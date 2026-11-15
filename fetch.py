"""Fetch one validated page; callers own pagination and publication."""

from dataclasses import dataclass
from pathlib import Path

import requests

from normalize import source_identifier
from raw_capture import save_response
from sources import SOURCES


@dataclass
class FetchedPage:
    source: str
    records: list[dict]
    capture_dir: Path
    offset: int
    page_size: int
    total_count: int | None


def fetch_page(source_name, *, raw_dir, ccn=None, page_size=500, offset=0, contract=None):
    """Return records and provenance without printing or claiming completeness.

    A captured HTTP body is evidence, not a successfully validated dataset.
    Parsing/filter failures raise errors while leaving that evidence available.
    """
    source = contract if contract is not None else SOURCES[source_name]
    maximum = 500 if source["family"] == "profile" else 5000
    if type(page_size) is not int or not 1 <= page_size <= maximum:
        raise ValueError(f"page_size must be an integer between 1 and {maximum}")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a nonnegative integer")
    if ccn is not None:
        ccn = source_identifier(ccn)

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
    else:
        url = f"https://data.cms.gov/data-api/v1/dataset/{dataset_id}/data"
        parameters = {"size": page_size, "offset": offset}
        if ccn is not None:
            parameters[f"filter[{source['ccn_field']}]"] = ccn

    response = requests.get(url, params=parameters, timeout=(5, 30))
    response.raise_for_status()
    capture = save_response(
        response,
        raw_dir=Path(raw_dir),
        source=source_name,
        dataset_id=dataset_id,
        parameters=parameters,
        scope={"year": source["year"], "ccn": ccn, "coverage": "single_page"},
    )

    try:
        payload = response.json()
        total_count = None
        if source["family"] == "profile":
            if not isinstance(payload, dict):
                raise ValueError("Expected a profile response object")
            records = payload.get("results")
            total_count = payload.get("count")
            if type(total_count) is not int or total_count < 0:
                raise ValueError("Expected a nonnegative profile count")
        else:
            records = payload
        if not isinstance(records, list):
            raise ValueError("Expected an array of records")
        if len(records) > page_size:
            raise ValueError("Response exceeded the requested page size")
        for row in records:
            if not isinstance(row, dict):
                raise ValueError("Expected each record to be an object")
            actual_ccn = source_identifier(row.get(source["ccn_field"]))
            if ccn is not None and actual_ccn != ccn:
                raise ValueError("Response contains an unexpected hospital CCN")
    except ValueError as error:
        raise ValueError(f"{error}; inspect raw evidence at {capture}") from error

    return FetchedPage(source_name, records, capture, offset, page_size, total_count)
