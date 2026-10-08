-- Run on results/inventory.sqlite. The area is clipped to the study square.
-- 1. Land classification: retain codes rather than guessing their meanings.
SELECT POLYTYPE, COUNT(*) AS features, SUM(area_ha) AS area_ha
FROM inventory GROUP BY POLYTYPE ORDER BY area_ha DESC;

-- 2. Quality flags by count and affected area.
SELECT age_flag, COUNT(*) AS features, SUM(area_ha) AS area_ha
FROM inventory GROUP BY age_flag;

-- 3. Candidate area for an illustrative 80-year threshold, not allowable harvest.
SELECT COUNT(*) AS features, SUM(area_ha) AS candidate_area_ha
FROM inventory WHERE age_valid = 1 AND age >= 80;

-- 4. Area-weighted age: large polygons should contribute more than small ones.
SELECT SUM(age * area_ha) / SUM(area_ha) AS area_weighted_age
FROM inventory WHERE age_valid = 1;

-- 5. Leading-species codes: no full-stand species composition is implied.
SELECT OLEADSPC, SUM(area_ha) AS area_ha
FROM inventory WHERE age_valid = 1 GROUP BY OLEADSPC ORDER BY area_ha DESC;
