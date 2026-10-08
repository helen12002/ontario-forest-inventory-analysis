"""Reproducible historical inventory screening, not an operational harvest plan.
Run: python analyze.py --source /path/to/source.gdb
"""
from pathlib import Path
import argparse, json, sqlite3, hashlib, shutil
import geopandas as gpd
import pandas as pd
import numpy as np
import pyogrio
import shapely
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True)
parser.add_argument('--thresholds', nargs='+', type=int, default=[60,80,90,100])
args = parser.parse_args()
src = Path(args.source)
layer = 'Ban_Mind_FRI'

# Inspect full-unit attributes cheaply; keep extent analysis intentionally small.
full = pyogrio.read_dataframe(src, layer=layer, read_geometry=False)
full_audit = {'records':len(full), 'duplicate_polyid_rows':int(full.POLYID.duplicated().sum()),
              'source_year_counts':{str(k):int(v) for k,v in full.YRSOURCE.value_counts().items()},
              'forest_age_over_300_rows':int(((full.POLYTYPE=='FOR') & (full.OAGE>300)).sum())}

# A 20 x 20 km square centred on Bancroft, Ontario (not a random sample).
cx,cy = Transformer.from_crs(4326,26917,always_xy=True).transform(-77.858,45.057)
bounds=(cx-10000,cy-10000,cx+10000,cy+10000)
cols=['POLYID','POLYTYPE','YRSOURCE','SOURCE','OAGE','OYRORG','OLEADSPC','OSPCOMP','MGMTCON1','MGMTCON2','MGMTCON3']
g = pyogrio.read_dataframe(src, layer=layer, columns=cols, bbox=bounds, fid_as_index=True)
g['source_fid']=g.index
g=g.reset_index(drop=True)
# The horizontal component is NAD83/UTM17N. Drop Z/M for planar area analysis.
g.geometry=shapely.force_2d(g.geometry)
g=g.set_crs(26917,allow_override=True)
g['geometry_repaired']=~g.geometry.is_valid
g.geometry=shapely.make_valid(g.geometry)
g.geometry=g.geometry.intersection(shapely.box(*bounds))
g=g[~g.geometry.is_empty & (g.geometry.area>0)].copy()
# Retain distinct features with repeated IDs. Deduplicate only exact same
# clipped geometry AND analysis attributes; record the count explicitly.
key=g[cols].astype(str).agg('|'.join,axis=1)+'|'+g.geometry.to_wkb(hex=True)
exact_dupes=int(key.duplicated().sum())
g=g.loc[~key.duplicated()].copy()
g['area_ha']=g.geometry.area/10000
g['duplicate_polyid']=g.POLYID.duplicated(keep=False)
g['forest']=g.POLYTYPE.eq('FOR')
g['age']=pd.to_numeric(g.OAGE,errors='coerce')
# 300 is a disclosed review cutoff, not a biological upper limit.
g['age_valid']=g.forest & g.age.notna() & g.age.between(1,300)
g['age_flag']=np.select([~g.forest,g.age.isna()|g.age.le(0),g.age.gt(300)],
                        ['not_FOR','missing_or_nonpositive','review_over_300'],default='usable')
g['age_band']=pd.cut(g.age,[0,20,40,60,80,100,150,300],
                     labels=['1–20','21–40','41–60','61–80','81–100','101–150','151–300']).astype('str')
g.loc[~g.age_valid,'age_band']='Excluded / non-forest'
for t in args.thresholds:
    g[f'age_ge_{t}']=g.age_valid & g.age.ge(t)

forest=g[g.forest].copy()
usable=g[g.age_valid].copy()
forest_area=float(forest.area_ha.sum())
usable_area=float(usable.area_ha.sum())
union_area=float(shapely.union_all(g.geometry).area/10000)
overlap=float(g.area_ha.sum()-union_area)
if overlap > max(0.01,union_area*1e-6):
    raise ValueError(f'Unresolved polygon overlap: {overlap:.4f} ha. Review before publishing sums.')
assert usable_area>0
summary=[]
for t in sorted(set(args.thresholds)):
    part=usable[usable.age>=t]
    summary.append({'threshold_years':t,'features':len(part),'candidate_area_ha':float(part.area_ha.sum()),
                    'pct_usable_forest':float(part.area_ha.sum()/usable_area*100)})
scenarios=pd.DataFrame(summary)
assert scenarios.candidate_area_ha.is_monotonic_decreasing
assert scenarios.candidate_area_ha.between(0,usable_area+1e-6).all()
scenarios.to_csv(OUT/'scenarios.csv',index=False)
usable.groupby('age_band',observed=True).area_ha.sum().to_csv(OUT/'age_area.csv')
usable.groupby('OLEADSPC',dropna=False).area_ha.sum().sort_values(ascending=False).to_csv(OUT/'leading_species_area.csv')
g.drop(columns='geometry').to_csv(OUT/'inventory.csv',index=False)
gpkg=OUT/'inventory.gpkg'
if gpkg.exists(): gpkg.unlink()
g.to_file(gpkg,layer='inventory',driver='GPKG')
gpd.GeoDataFrame({'label':['20 km study square']},geometry=[shapely.box(*bounds)],crs=26917).to_file(gpkg,layer='study_boundary',driver='GPKG')
db=OUT/'inventory.sqlite'
with sqlite3.connect(db) as con:
    g.drop(columns='geometry').to_sql('inventory',con,if_exists='replace',index=False)
    sql=con.execute('SELECT SUM(area_ha) FROM inventory WHERE age_valid=1').fetchone()[0]
    assert abs(sql-usable_area)<1e-6

audit={'full_unit':full_audit,'study_bounds_utm17':bounds,'study_square_ha':40000,
       'intersecting_records_after_dedup':len(g),'exact_duplicates_removed':exact_dupes,
       'duplicate_polyid_records_retained':int(g.duplicate_polyid.sum()),
       'repaired_geometry_records':int(g.geometry_repaired.sum()),'covered_area_ha':union_area,
       'overlap_ha':overlap,'forest_area_ha':forest_area,'usable_forest_area_ha':usable_area,
       'excluded_forest_area_ha':forest_area-usable_area,
       'excluded_forest_age_records':int((forest.age_valid==False).sum()),
       'max_forest_age':float(forest.age.max()),
       'area_weighted_age':float((usable.age*usable.area_ha).sum()/usable_area),
       'study_source_years':sorted(g.YRSOURCE.dropna().unique().astype(int).tolist())}
(OUT/'audit.json').write_text(json.dumps(audit,indent=2))

def finish_map(ax,title,subtitle):
    ax.set_title(title+'\n'+subtitle,loc='left',fontsize=12,pad=15)
    ax.set_xlim(bounds[0],bounds[2]); ax.set_ylim(bounds[1],bounds[3]); ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([])
    ax.annotate('Grid N ↑',xy=(.88,.94),xycoords='axes fraction',ha='center',fontsize=11)
    x,y=bounds[0]+1000,bounds[1]+1000
    ax.plot([x,x+5000],[y,y],color='#172f2b',lw=3); ax.text(x+2500,y+400,'5 km',ha='center')

fig,ax=plt.subplots(figsize=(8,8))
g.plot(ax=ax,color='#e7e9e5',linewidth=0)
usable.plot(ax=ax,column='age',cmap='YlGnBu',vmin=0,vmax=150,legend=True,
            legend_kwds={'label':'Recorded overstorey age (years; colour capped at 150)','shrink':.65},linewidth=0)
finish_map(ax,'Bancroft historical forest inventory','20 × 20 km study square | source year 2007')
fig.text(.08,.02,'Grey: non-FOR or excluded age. Source: Ontario FRI v2, Bancroft–Minden package.',fontsize=8)
fig.savefig(OUT/'age_map.png',dpi=170,bbox_inches='tight');plt.close(fig)

fig,axes=plt.subplots(1,len(scenarios),figsize=(5*len(scenarios),6),squeeze=False)
for ax,row in zip(axes[0],summary):
    g.plot(ax=ax,color='#eceeea',linewidth=0)
    usable[usable.age>=row['threshold_years']].plot(ax=ax,color='#177d66',linewidth=0)
    finish_map(ax,f"Age ≥ {row['threshold_years']} years",f"{row['candidate_area_ha']:,.0f} ha | {row['pct_usable_forest']:.1f}% of usable FOR")
fig.text(.03,.02,'Green: age-screen candidates only. Illustrative thresholds; no operational, ownership or habitat exclusions.',fontsize=9)
fig.savefig(OUT/'scenario_maps.png',dpi=160,bbox_inches='tight');plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(11,4.8))
bands=['1–20','21–40','41–60','61–80','81–100','101–150','151–300']
band_area=usable.groupby('age_band',observed=True).area_ha.sum().reindex(bands,fill_value=0)
axes[0].bar(band_area.index,band_area.values,color='#177d66')
axes[0].tick_params(axis='x',rotation=35)
axes[0].set(xlabel='Recorded age band (years; unequal intervals)',ylabel='Area (ha)',title='Forest area by recorded age band')
axes[1].bar(scenarios.threshold_years.astype(str),scenarios.candidate_area_ha,color=plt.cm.Greens(np.linspace(.4,.9,len(scenarios))))
axes[1].set(xlabel='Illustrative minimum age (years)',ylabel='Candidate area (ha)',title='Sensitivity to the age threshold')
for i,row in enumerate(summary): axes[1].text(i,row['candidate_area_ha'],f"{row['candidate_area_ha']:,.0f}",ha='center',va='bottom')
axes[1].set_ylim(0,scenarios.candidate_area_ha.max()*1.2)
fig.tight_layout();fig.savefig(OUT/'analysis_charts.png',dpi=170);plt.close(fig)

table=scenarios.to_html(index=False,float_format=lambda x:f'{x:,.1f}',border=0)
report=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Historical forest inventory screening</title>
<style>body{{font:16px/1.6 system-ui;max-width:1000px;margin:45px auto;padding:0 24px;color:#17382f}}h1{{font-size:32px;line-height:1.2}}h2{{margin-top:35px}}img{{max-width:100%}}table{{border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #ccd8d2}}.note{{background:#edf4ef;padding:18px}}</style>
<p>PORTFOLIO STUDY · HISTORICAL INVENTORY · 8 OCTOBER 2026</p>
<h1>Forest Inventory Analysis and Age-Threshold Scenario Screening</h1>
<p>Bancroft–Minden FRI v2 · 20 × 20 km study square centred at 45.057°N, 77.858°W</p>
<p class="note">This study screens recorded forest age under illustrative thresholds. It does not determine allowable harvest, ecological sustainability or current forest conditions.</p>
<h2>Question and findings</h2><p>How does the recorded age structure affect the area passing a simple age screen? The clipped study contains {forest_area:,.1f} ha coded FOR; {usable_area:,.1f} ha have ages usable under the disclosed quality rule. The area-weighted mean recorded age is {audit['area_weighted_age']:.1f} years.</p>
{table}<img src="analysis_charts.png" alt="Age distribution and threshold comparison">
<h2>Data and method</h2><p>Downloaded the Ontario official Bancroft–Minden 2008 2D package. All {len(full):,} source-layer records have YRSOURCE=2007. Ages were used as recorded, without adding elapsed years. The square is an intentionally selected local study extent, not a representative sample of the entire management unit.</p>
<p>Read Ban_Mind_FRI, retained source feature IDs, dropped vertical coordinates, validated geometry and clipped to the square. Calculated planar area in NAD83 / UTM zone 17N, dividing square metres by 10,000. Selected POLYTYPE=FOR. OAGE is treated as the recorded overstorey-age field; mixed-age stands are not fully represented by one age. Exact geometry-and-attribute duplicates were removed ({exact_dupes}); repeated polygon identifiers alone were retained.</p>
<h2>Quality review</h2><p>The full unit has {full_audit['duplicate_polyid_rows']:,} repeated-ID rows and {full_audit['forest_age_over_300_rows']} FOR records with OAGE above 300. These are review flags, not proven errors. In the study area {audit['excluded_forest_age_records']} forest records, totalling {audit['excluded_forest_area_ha']:,.2f} ha, fail the age rule (missing/nonpositive or above 300). The 300-year cutoff is an analyst-selected review limit, not a biological claim. Repaired geometries: {audit['repaired_geometry_records']}. Remaining area overlap: {overlap:.6f} ha. SQL and Python area totals agree; candidate area declines monotonically as the threshold increases.</p>
<img src="age_map.png" alt="Recorded age map"><img src="scenario_maps.png" alt="Age threshold maps">
<h2>Applicant-created QGIS map</h2><p>The applicant independently applied the 90-year filter in QGIS, checked 664 polygons and 11,447.9 ha using Statistical Summary, and created this print layout with a scale bar and source attribution.</p><img src="../age_screen_90.png" alt="Applicant-created QGIS map for the 90-year scenario"><h2>Interpretation and limits</h2><p>Raising the threshold narrows the set of polygons satisfying this single rule. The scenarios are nested screening sets, not selected harvest schedules. Thresholds of 60, 80, 90 and 100 years are teaching assumptions, not policy, species-specific maturity criteria or recommendations. Older forest area is not a complete biodiversity measure.</p>
<p>No ownership, protected-area, water-buffer, habitat, access, silvicultural-system or management-constraint exclusions have been applied. Historical data and one overstorey age cannot establish operational eligibility. For uneven-aged hardwood stands, age-only screening is particularly limited. No timber volume, growth, disturbance, renewal, harvest timing or socioeconomic impacts are modelled.</p>
<h2>Next steps</h2><p>Confirm field definitions and flagged ages with the authoritative technical specification; add land tenure and management constraints; use species-appropriate growth/yield and silvicultural rules; then explore multi-period scenarios and validate assumptions with forestry staff.</p>
<h2>Sources and reproducibility</h2><p><a href="https://www.arcgis.com/home/item.html?id=9de0dad6f1b3435eb46df8ee49f4ecfd">Ontario FRI v2 official catalogue</a> · <a href="https://ws.gisetl.lrc.gov.on.ca/fmedatadownload/Packages/pp_FRI_FIMv2_BancroftMindenForest_2008_2D.zip">Source package</a> · <a href="https://www.ontario.ca/page/open-government-licence-ontario">Open Government Licence – Ontario</a>. Contains information licensed under the Open Government Licence – Ontario.</p>
<p>Analysis: Python, GeoPandas, Shapely, Pyogrio, pandas, SQLite and Matplotlib. See analyze.py, audit.json, inventory.csv, scenarios.csv and inventory.gpkg. AI assisted implementation; the applicant should independently review the method and reproduce one parameter change before presenting it.</p></html>'''
(OUT/'report.html').write_text(report)
print(json.dumps(audit,indent=2));print(scenarios.to_string(index=False))
