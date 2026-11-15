## Implementation

### `sources.py`

- Stores a dict containing the source configuration, not the database schema.

```python
"inpatient": {
    "family": "data",
    "dataset_id": "2f1e57ea-ac2f-4f62-aeb1-f8254307c395",
    "ccn_field": "Rndrng_Prvdr_CCN",
    "year": 2023,
}
```

- `family`: which API format to use.
- `dataset_id`: which release to request.
- `ccn_field`: what that source calls its hospital identifier.
- `year`: the year of the release. Profiles use `None` because they are current profiles.

These are still the original defaults for manual inspection. The full refresh gets updated source configurations from `catalog.py`, so it does not stay on 2023.

### `catalog.py`

Finds the latest year shared by cost and inpatient data.

- Reads CMS's dataset catalog at `https://data.cms.gov/data.json`.
- Finds the cost and inpatient releases and their version-specific API URLs.
- Reads current hospital profile metadata from the provider-data catalog.
- Saves the metadata so we can inspect what was used.

```python
common = versions["cost"].keys() & versions["inpatient"].keys()
if not common:
    raise ValueError("No common cost/inpatient year found")
year = max(common)
```

This finds years that exist in both datasets, then chooses the most recent one.

If cost has 2024 and 2025 but inpatient only has 2024, we use 2024 for both.

- On October 22, 2026, the verified latest common year was **2024**.
- Profiles are still the current snapshot. Their ratings should not be described as 2024 ratings.

### `fetch.py`

```python
def fetch_page(source_name, *, raw_dir, ccn=None, page_size=500, offset=0, contract=None):
    source = contract if contract is not None else SOURCES[source_name]
```

- `raw_dir`: where to save the response.
- `ccn=None`: no hospital filter unless supplied.
- `page_size`: maximum records requested.
- `offset`: how many matching records to skip.
- `contract`: updated source configuration from the catalog. Uses `SOURCES` if not supplied.
- `*`: the remaining arguments must be passed by name.

We then reject invalid params like impossible values for page size or offset.

- Profile requests are limited by our code to 500 records per page; data requests to 5,000.
- `source_identifier()` checks for six letters or digits and preserves leading zeros.
- We allow letters because the full profile dataset contains legitimate alphanumeric identifiers. The earlier numeric-only helper was too restrictive for the full dataset.

We then build the API request, either profile or data.

**Profile**

```python
dataset_id = source["dataset_id"]
if source["family"] == "profile":
    url = f"https://data.cms.gov/provider-data/api/1/datastore/query/{dataset_id}/0"
    parameters = {"limit": page_size, "offset": offset}
    if ccn is not None:
        parameters.update({
            "conditions[0][property]": source["ccn_field"],
            "conditions[0][value]": ccn,
            "conditions[0][operator]": "=",
        })
```

Profile calls the hospital profile info.

- Hospital identifier, name, state and general metrics.
- One row per hospital in the current snapshot.

**Data**

```python
else:
    url = f"https://data.cms.gov/data-api/v1/dataset/{dataset_id}/data"
    parameters = {"size": page_size, "offset": offset}
    if ccn is not None:
        parameters[f"filter[{source['ccn_field']}]"] = ccn
```

Cost and inpatient use the same API family, with different dataset IDs.

- Cost: one row per hospital cost report. A hospital can have multiple reports.
- Inpatient: one row per hospital and DRG within the selected year. DRG is a group of inpatient cases.
- These are financial reports and aggregated statistics, not individual bills or patient visits.

Then we send the request and check the HTTP status.

```python
response = requests.get(url, params=parameters, timeout=(5, 30))
response.raise_for_status()
```

- Five-second connection timeout and 30-second read timeout.
- These are not a total time limit for the entire dataset refresh.

Then we preserve the successful response before parsing or cleaning it.

```python
capture = save_response(
    response,
    raw_dir=Path(raw_dir),
    source=source_name,
    dataset_id=dataset_id,
    parameters=parameters,
    scope={"year": source["year"], "ccn": ccn, "coverage": "single_page"},
)
```

- Records `single_page` because one request does not prove the whole dataset was fetched.
- If parsing or validation fails afterwards, we still have the response to inspect.
- An HTTP error raises before this capture step. That error body is not saved by this function.

Then extract records from the HTTP response:

```python
if source["family"] == "profile":
    if not isinstance(payload, dict):
        raise ValueError("Expected a profile response object")
    records = payload.get("results")
    total_count = payload.get("count")
    if type(total_count) is not int or total_count < 0:
        raise ValueError("Expected a nonnegative profile count")
else:
    records = payload
```

Checks that the profile payload is a dict, extracts its list of records, then checks that the total count is an integer greater than or equal to zero.

This extracts a list from the surrounding dict. Cost and inpatient APIs already return a list of record dicts, so we set `records` to the payload.

Then check the records:

```python
if not isinstance(records, list):
    raise ValueError("Expected an array of records")
if len(records) > page_size:
    raise ValueError("Response exceeded the requested page size")
```

For every record, we validate its identifier and, if a hospital was requested, check that it matches.

This checks **our filter expectation**, even if the HTTP request succeeded. It does not yet validate payment fields, duplicate row keys or dataset completeness.

Finally, return a `FetchedPage` object:

```python
return FetchedPage(source_name, records, capture, offset, page_size, total_count)
```

### `raw_capture.py`

Saves the unchanged response body and a manifest describing the request.

- Response body goes in `response.json`.
- Manifest records the URL, parameters, source, release, retrieval time and response hash.
- Raw captures go under `data/raw/` during a full refresh.

If our cleaning is wrong, we can retest it with the exact same input instead of refetching potentially different data.

### `ingest.py`

`all_pages()` uses `fetch_page()` repeatedly to fetch the whole source.

```python
offset += len(page.records)
```

We move the offset by how many records actually came back.

- For profiles, we stop when we reach the reported total count.
- For cost and inpatient, we keep going until an empty page comes back.
- A short data page alone does not make us stop.

We also reject repeated pages, duplicate row keys, changing profile counts and extracts over the safety cap.

The row key depends on what one row represents:

- Profile: hospital identifier.
- Cost: report ID.
- Inpatient: hospital identifier and DRG, within this selected release.

CCN connects the sources, but it is not a unique row key in every source.

### `store.py` and `schema.sql`

`store.py` converts selected source fields into values we can query and inserts them into SQLite.

- Identifiers stay as text so leading zeros survive.
- Numeric strings become numbers.
- Missing or unavailable values become `None`, which SQLite stores as `NULL`.
- Original missing markers stay in `status_json`.
- Unexpected numeric values cause the refresh to fail instead of silently becoming zero.

```python
if value is None or (isinstance(value, str) and value.strip() in MISSING):
    statuses[field] = value
    return None
```

Missing payment and zero payment are different. We do not want missing values lowering an average as though they were actual zeros.

Every original field is also retained in `raw_json`. `row_hash` is calculated from the source record so we can detect changed records between refreshes.

`schema.sql` defines the tables:

- `profiles`: one row per hospital identifier.
- `cost_reports`: one row per report ID, including fiscal dates.
- `inpatient`: one row per hospital and DRG in the selected release.
- `source_versions`: which releases were loaded, when they were checked, row counts and changes.

Then it defines `hospital_results`, a SQL view. A view stores a query, not a separate joined copy of the data.

- Starts with inpatient records.
- Left-joins hospital profile information by hospital identifier.
- Joins cost values only when there is exactly one report and its fiscal period overlaps the inpatient year.
- Missing matches keep the inpatient row, with missing context.
- Multiple reports produce `cost_status = 'ambiguous'` and no selected cost values.

This avoids multiplying an inpatient row by several cost reports or guessing which report to use.

Fiscal overlap does not mean the periods are identical. Hospital-wide finances also repeat across a hospital's DRGs, so we must not sum them across the joined rows.

### `refresh.py`

Runs the full process:

1. Take a lock so two refreshes cannot publish at once.
2. Resolve the latest common year and save source metadata.
3. Fetch every page into raw storage.
4. Normalize and load separate tables in a temporary database.
5. Compare source record hashes with the previous snapshot.
6. Recheck metadata and validate the database and join row count.
7. Replace the published database only after the checks pass.

```python
os.replace(staging, current)
```

The replacement publishes the completed database in one filesystem operation. Queries do not see half of a refresh.

If downloading or validation fails before publication, the previous database remains available. The failed attempt is recorded in `data/status.json` and its captured raw pages remain available.

- `retrieved_at`: when we loaded the source this time.
- `last_data_change`: when this pipeline last observed changed source records.
- Added, removed, changed and unchanged counts describe differences from the previous snapshot.
- A newly selected year starts a new baseline.

We download the full selected releases each day and compare them locally. This is not a source-provided incremental update feed.

### `query.py`

Opens the published database read-only and queries the joined view.

First, open a terminal in the project:

```bash
cd /Users/jacob/school/hospital-explorer
```

Fetch or refresh the complete datasets:

```bash
.venv/bin/python refresh.py
```

Query one hospital and DRG:

```bash
.venv/bin/python query.py --ccn 010001 --drg 871
```

Compare records for the same DRG across hospitals:

```bash
.venv/bin/python query.py --drg 871 --limit 100
```

Check the latest refresh attempt and published source information:

```bash
.venv/bin/python query.py --status
```

Queries perform the joins against locally saved tables. They do not make fresh API calls.

### Daily refresh

The Mac job is installed to run at **5 a.m. Pacific**, using the Mac's current Pacific timezone.

- Runs the same `refresh.py` command.
- Requires a logged-in session; a sleeping Mac can run the missed event on waking.
- It is not an always-on service when the Mac is off or logged out.
- Logs are in `data/scheduled-refresh.log` and `data/scheduled-refresh-error.log`.
- Raw responses are retained; there is no automatic cleanup policy yet.

Daily refresh means checking for new published data. It does not mean CMS produces new records every day.

### `inspect_source.py`

This is still a **manual inspection tool**: it fetches one page, prints it and tells you where the raw response was saved.

```bash
# Cost reports for hospital 010001, using the original 2023 default
.venv/bin/python inspect_source.py cost --ccn 010001

# Inpatient records using the original 2023 default
.venv/bin/python inspect_source.py inpatient --ccn 010001

# Current general profile
.venv/bin/python inspect_source.py hospital_general_information --ccn 010001
```

By default, each command requests **up to two records**. To request more, append `--page-size 10`.

Use this to inspect source records while developing the integration. It does not join datasets or fetch every page. The full refresh uses the same retrieval function with the catalog-resolved release.

### Verification

```bash
.venv/bin/python -m unittest discover -v
```

- 19 tests passed.
- Full live ingestion loaded 5,419 profiles, 6,109 cost reports and 145,879 inpatient rows.
- The joined view also contains 145,879 rows, so the joins did not drop or multiply inpatient records.
- A repeated refresh reported zero added, removed or changed records.
- Tests verify that a simulated refresh failure preserves the previous database, and missing payments stay missing.

These are verified results from October 22, 2026. The sources can change later.

The completeness checks rely on the APIs' paging behavior. We check metadata before and after the run, but that does not prove all three upstream sources were frozen at exactly the same moment.
