# Forest Inventory Analysis and Age-Threshold Scenario Screening

Completed portfolio case study — 8 October 2026

## Objective

Build a reproducible workflow that integrates historical Ontario forest inventory attributes and geometries, checks data quality, and compares the area passing illustrative age thresholds. Demonstrate skills relevant to Forest Analyst Intern: Python, SQL, GIS, information management and technical communication.

## Data and workflow

Used the official Bancroft–Minden FRI v2 package, with source-year field 2007, and selected a 20 × 20 km square near Bancroft. Read the source geodatabase, repaired four selected geometries, clipped polygons and calculated area in NAD83 / UTM zone 17N. Preserved source identifiers and management-constraint fields. Selected forest records coded FOR and screened recorded overstorey ages for missing/nonpositive and flagged extreme values. No forest records in the local study failed that quality rule.

The full source layer contains 110,053 records, repeated polygon identifiers, and one age above the analyst-selected 300-year review cutoff. These flags require review; they do not prove errors. Local coverage is 40,000 ha with no meaningful overlap. The study includes 3,581 polygons and 31,063.52 ha of usable forest.

## Results

| Illustrative minimum age | Polygons | Candidate area (ha) | Share of usable forest |
|---|---:|---:|---:|
| 60 | 1,739 | 27,191.03 | 87.5% |
| 80 | 1,162 | 19,432.53 | 62.6% |
| 90 | 664 | 11,447.93 | 36.9% |
| 100 | 183 | 3,431.37 | 11.0% |

Increasing the threshold from 80 to 90 years reduces candidate area by 7,984.60 ha, or 41.1%. This demonstrates sensitivity to a single screening assumption. It does not establish that either threshold is appropriate for the forest. The area's weighted mean recorded age is 76.99 years.

## Validation and contributions

Python and SQL area totals agree. Scenario areas decrease monotonically as the threshold rises. The applicant independently reproduced the 80- and 90-year filters in QGIS, checked the 90-year count and area with Statistical Summary, and exported a layout with title, scale bar, findings and attribution. Python implementation, automated checks and report preparation were assisted by AI. The QGIS project uses relative data paths and is included in the package.

## Limits and next steps

This is a historical inventory analysis and age-screening exercise, not a forest estate simulation, current inventory forecast or allowable-harvest determination. The age thresholds are educational assumptions. Ownership, protection, habitat, water buffers, access and silvicultural constraints have not been applied. One overstorey age cannot fully describe an uneven-aged stand. Growth/yield, regeneration, disturbance, wood volume and socioeconomic impacts are not modelled.

Extend the work by verifying field semantics against authoritative technical specifications, adding operational and ecological constraints, and introducing species-appropriate growth/yield and renewal parameters for a multi-period model.

## Source

Ontario Ministry of Natural Resources / Land Information Ontario, Forest Resources Inventory Packaged Products – Version 2, Bancroft–Minden package. Contains information licensed under the Open Government Licence – Ontario. Official catalogue: https://www.arcgis.com/home/item.html?id=9de0dad6f1b3435eb46df8ee49f4ecfd

