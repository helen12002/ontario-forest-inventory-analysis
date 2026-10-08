"""Restore the included study GeoPackage for QGIS, using only Python's standard library."""
from pathlib import Path
import zipfile
root = Path(__file__).resolve().parent
with zipfile.ZipFile(root / "data/inventory.gpkg.zip") as archive:
    archive.extract("inventory.gpkg", root / "results")
print("Ready: open my_forest_analysis.qgz in QGIS.")
