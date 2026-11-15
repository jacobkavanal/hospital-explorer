# Hospital integration

Fetch complete national CMS releases, retain raw responses, validate and store separate SQLite tables, and join them when queried. No agent or web interface is required.

## Use

Run from `/Users/jacob/school/hospital-explorer`:

```bash
.venv/bin/python refresh.py
.venv/bin/python query.py --ccn 010001 --drg 871
.venv/bin/python query.py --drg 871 --limit 100
.venv/bin/python query.py --status
.venv/bin/python -m unittest discover -v
```

`refresh.py` discovers the latest year available in both historical datasets. It fetches that entire year plus current hospital profiles, not every historical year. On October 22, 2026, the selected year was 2024. A new common year replaces the published snapshot and starts a new change-count baseline. Raw captures of previous refreshes remain available.

The manual inspection tool still uses the original 2023 defaults in `sources.py`:

```bash
.venv/bin/python inspect_source.py cost --ccn 010001
```

## Files

- `sources.py`: base API contracts and manual inspection defaults.
- `catalog.py`: current metadata and latest common release resolution.
- `fetch.py`: one request, successful-response capture, envelope and identifier validation.
- `raw_capture.py`: original response bytes and request manifest.
- `ingest.py`: full pagination and unique source-key checks.
- `normalize.py`: identifier helpers; `store.py`: typed fields, missing markers, hashes and inserts.
- `schema.sql`: source tables, provenance table and query-time views.
- `refresh.py`: lock, staging, validation, change counts and atomic publication.
- `query.py`: read-only filtered queries and freshness inspection.
- `launchd/`: installed daily-job configuration copy.
- `implementation-notes.md`: step-by-step notes in the original learning-note style.

## Data and joins

Profiles have one row per source hospital identifier; cost reports have one row per report ID; inpatient rows have one row per hospital and DRG in the selected release. These are published aggregates, not individual patient records. Identifiers remain text, including legitimate alphanumeric profile identifiers.

Every source field survives in `raw_json`; selected fields are typed for queries. Missing markers become SQL NULL with original markers in `status_json`. Unexpected numeric formats fail the refresh. Financial columns use SQLite REAL for exploratory analysis; original exact source values remain in JSON.

The `hospital_results` view starts with inpatient rows and left-joins profile and cost context. Multiple cost reports are marked ambiguous and financial values withheld, rather than selecting one arbitrarily. A single cost report must overlap the inpatient year. Overlap does not establish calendar-year comparability. Current profile ratings are not historical ratings. Hospital-wide financial values repeat across DRGs and must not be summed across the joined results.

## Daily refresh

Installed and loaded at:
`/Users/jacob/Library/LaunchAgents/com.jacob.hospital-explorer.refresh.plist`.

The job runs at 5 a.m. in the Mac's local timezone, currently America/Los_Angeles, including daylight saving changes. Keep the Mac set to Pacific time. It is a user LaunchAgent and requires a logged-in session. A sleeping Mac can run a missed calendar event on waking; this is not an always-on service or a guarantee of recovery after shutdown/logout. Run `refresh.py` manually if a check was missed.

Logs: `data/scheduled-refresh.log` and `data/scheduled-refresh-error.log`. Inspect `query.py --status` for latest attempt versus published data freshness. A failed refresh leaves the previous published database intact. No automatic same-day retry or notification is configured.

## Verification, October 22, 2026

Live national ingestion and repeat refresh succeeded:

| Source | Rows |
|---|---:|
| Current hospital profiles | 5,419 |
| 2024 cost reports | 6,109 |
| 2024 inpatient aggregates | 145,879 |

The joined view has 145,879 rows. Cost context: 144,536 matched, 1,174 ambiguous, 169 missing. Profile context: 145,538 matched and 341 missing. Repeat ingestion reported no record changes. A hospital/DRG query for `010001` / `871` returned one matched result.

Tests cover request validation/raw evidence, identifiers, latest common year, pagination, repeated pages, missing values, ambiguity, unchanged refreshes and preservation of the old database after a simulated failure.

## Limits

Each daily check downloads full selected releases, then compares record hashes. There is no verified source delta feed. Metadata is checked before and after retrieval, but CMS does not provide a verified transactionally consistent snapshot across these APIs. An empty terminal data page plus duplicate checks is an operational completeness check, not independent proof against every upstream omission.

Raw captures are retained without an automatic deletion policy; monitor disk usage. The one-million-row safety cap per source fails closed. The local CLI demonstrates reusable integration stages but does not establish production scalability, schema migration, reconciliation of ambiguous cost reports, or company ownership mapping. Future CIK joins need a separate dated ownership crosswalk; CIK must not replace hospital identity.
