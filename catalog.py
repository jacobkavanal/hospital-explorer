"""Resolve version-specific APIs for the latest common historical year."""

import json
import re
from pathlib import Path

import requests

from sources import SOURCES


CATALOG_URL = "https://data.cms.gov/data.json"
PROFILE_URL = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items"
TITLES = {
    "cost": "Hospital Provider Cost Report",
    "inpatient": "Medicare Inpatient Hospitals - by Provider and Service",
}


def resolve(catalog, profile):
    versions = {name: {} for name in TITLES}
    for dataset in catalog["dataset"]:
        for name, title in TITLES.items():
            if dataset.get("landingPage", {}).get("title") != title:
                continue
            periods = dataset.get("temporal", [])
            if len(periods) != 1:
                continue
            year = int(periods[0]["endDate"][:4])
            apis = [d for d in dataset.get("distribution", [])
                    if d.get("format") == "API" and d.get("description") != "latest"]
            if len(apis) != 1:
                raise ValueError(f"Ambiguous version-specific API: {title}, {year}")
            match = re.fullmatch(r"https://data.cms.gov/data-api/v1/dataset/([\w-]+)/data", apis[0]["accessURL"])
            if match is None or year in versions[name]:
                raise ValueError(f"Ambiguous dataset version: {title}, {year}")
            versions[name][year] = {
                **SOURCES[name], "dataset_id": match[1], "year": year,
                "metadata": dataset,
            }
    common = versions["cost"].keys() & versions["inpatient"].keys()
    if not common:
        raise ValueError("No common cost/inpatient year found")
    year = max(common)
    return {
        "hospital_general_information": {**SOURCES["hospital_general_information"], "metadata": profile},
        **{name: choices[year] for name, choices in versions.items()},
    }


def read_catalogs(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    objects = []
    for name, url in [("catalog", CATALOG_URL), ("profile", PROFILE_URL)]:
        response = requests.get(url, timeout=(10, 60))
        response.raise_for_status()
        (directory / f"{name}.json").write_bytes(response.content)
        objects.append(response.json())
    profiles = [entry for entry in objects[1] if entry.get("identifier") == "xubh-q36u"]
    if len(profiles) != 1:
        raise ValueError("Profile catalog must contain exactly one xubh-q36u entry")
    return resolve(objects[0], profiles[0])


def signature(contracts):
    return json.dumps(contracts, sort_keys=True, separators=(",", ":"))
