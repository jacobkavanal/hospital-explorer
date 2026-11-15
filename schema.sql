CREATE TABLE source_versions (
 source TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, year INTEGER,
 retrieved_at TEXT NOT NULL, last_data_change TEXT NOT NULL,
 row_count INTEGER NOT NULL, metadata_json TEXT NOT NULL,
 pages_json TEXT NOT NULL, changes_json TEXT NOT NULL
);
CREATE TABLE profiles (
 ccn TEXT PRIMARY KEY, name TEXT, state TEXT, rating INTEGER,
 status_json TEXT NOT NULL, raw_json TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE cost_reports (
 report_id TEXT PRIMARY KEY, ccn TEXT NOT NULL, fiscal_start TEXT NOT NULL,
 fiscal_end TEXT NOT NULL, net_revenue REAL, operating_expense REAL,
 income_patient_services REAL, status_json TEXT NOT NULL,
 raw_json TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE INDEX cost_ccn ON cost_reports(ccn);
CREATE TABLE inpatient (
 ccn TEXT NOT NULL, drg TEXT NOT NULL, description TEXT, discharges INTEGER,
 avg_charges REAL, avg_total_payment REAL, avg_medicare_payment REAL,
 status_json TEXT NOT NULL, raw_json TEXT NOT NULL, row_hash TEXT NOT NULL,
 PRIMARY KEY (ccn, drg)
);
-- Views execute at query time. No joined result table is stored.
CREATE VIEW cost_counts AS
 SELECT ccn, count(*) AS report_count FROM cost_reports GROUP BY ccn;
CREATE VIEW hospital_results AS
 SELECT i.ccn, i.drg, v.year AS inpatient_year, p.name, p.state, p.rating,
 i.description, i.discharges, i.avg_charges, i.avg_total_payment,
 i.avg_medicare_payment, c.report_id, c.fiscal_start, c.fiscal_end,
 c.net_revenue, c.operating_expense, c.income_patient_services,
 coalesce(n.report_count, 0) AS cost_report_count,
 CASE WHEN n.report_count IS NULL THEN 'missing'
      WHEN n.report_count > 1 THEN 'ambiguous'
      WHEN c.report_id IS NULL THEN 'period_mismatch'
      ELSE 'matched' END AS cost_status,
 CASE WHEN p.ccn IS NULL THEN 'missing' ELSE 'matched' END AS profile_status
 FROM inpatient i
 JOIN source_versions v ON v.source = 'inpatient'
 LEFT JOIN profiles p ON p.ccn = i.ccn
 LEFT JOIN cost_counts n ON n.ccn = i.ccn
 LEFT JOIN cost_reports c ON c.ccn = i.ccn AND n.report_count = 1
   AND c.fiscal_start <= printf('%04d-12-31', v.year)
   AND c.fiscal_end >= printf('%04d-01-01', v.year);
