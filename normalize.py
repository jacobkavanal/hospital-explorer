"""Small, explicit normalization rules for our hospital cohort."""

import re


from sources import SOURCES


def source_identifier(value):
    """Preserve national-source IDs, including VA/military alphanumeric IDs."""
    if not isinstance(value, str) or re.fullmatch(r"[0-9A-Za-z]{6}", value.strip()) is None:
        raise ValueError(f"Expected a six-character source identifier, got {value!r}")
    return value.strip()


def normalize_ccn(value):
    """Accept six ASCII digits as text; never guess missing leading zeros."""
    if not isinstance(value, str):
        raise ValueError("CCN must arrive as text")
    ccn = value.strip()
    if re.fullmatch(r"[0-9]{6}", ccn) is None:
        raise ValueError(f"Expected a six-digit hospital CCN, got {value!r}")
    return ccn


def extract_ccn(source, row):
    """Read hospital identity without changing the source record."""
    field = SOURCES[source]["ccn_field"]
    return normalize_ccn(row.get(field))
