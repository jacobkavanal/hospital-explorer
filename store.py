"""Store separate source tables and preserve all original columns as JSON."""

from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from normalize import source_identifier

TABLES = {"hospital_general_information": "profiles", "cost": "cost_reports", "inpatient": "inpatient"}
MISSING = {"", "Not Available", "Not Applicable", "N/A", "*", "--"}


def number(row, field, statuses, *, integer=False):
    if field not in row:
        raise ValueError(f"Required field missing: {field}")
    value = row[field]
    if value is None or (isinstance(value, str) and value.strip() in MISSING):
        statuses[field] = value
        return None
    try:
        parsed = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise ValueError(f"Unexpected numeric value: {field}={value!r}") from error
    if not parsed.is_finite() or (integer and parsed != parsed.to_integral_value()):
        raise ValueError(f"Invalid numeric value: {field}={value!r}")
    return int(parsed) if integer else float(parsed)


def normalized_row(source, row):
    statuses = {}
    raw = json.dumps(row, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    if source == "hospital_general_information":
        values = [source_identifier(row["facility_id"]), row["facility_name"], row["state"],
                  number(row, "hospital_overall_rating", statuses, integer=True)]
        if values[3] is not None and values[3] not in range(1, 6):
            raise ValueError("Rating outside 1–5")
    elif source == "cost":
        report = row["rpt_rec_num"]
        if not isinstance(report, str) or not re.fullmatch(r"[0-9]+", report):
            raise ValueError("Invalid cost report identifier")
        start, end = row["Fiscal Year Begin Date"], row["Fiscal Year End Date"]
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("Reversed fiscal interval")
        values = [report, source_identifier(row["Provider CCN"]), start, end]
        values += [number(row, field, statuses) for field in (
            "Net Patient Revenue", "Less Total Operating Expense", "Net Income from Service to Patients")]
    else:
        drg = row["DRG_Cd"]
        if not isinstance(drg, str) or not re.fullmatch(r"[0-9]{3}", drg):
            raise ValueError(f"Invalid DRG code: {drg!r}")
        count = number(row, "Tot_Dschrgs", statuses, integer=True)
        if count is not None and count < 0:
            raise ValueError("Negative discharge count")
        values = [source_identifier(row["Rndrng_Prvdr_CCN"]), drg, row["DRG_Desc"], count]
        values += [number(row, field, statuses) for field in (
            "Avg_Submtd_Cvrd_Chrg", "Avg_Tot_Pymt_Amt", "Avg_Mdcr_Pymt_Amt")]
    return values + [json.dumps(statuses), raw, digest]


def initialize(path):
    db = sqlite3.connect(path)
    db.executescript(Path(__file__).with_name("schema.sql").read_text())
    return db


def insert_page(db, source, records):
    table = TABLES[source]
    for record in records:
        values = normalized_row(source, record)
        db.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in values)})", values)


def row_hashes(db, source):
    table = TABLES[source]
    keys = "report_id" if source == "cost" else "ccn, drg" if source == "inpatient" else "ccn"
    return {tuple(row[:-1]): row[-1] for row in db.execute(f"SELECT {keys}, row_hash FROM {table}")}


def compare(previous, current):
    return {
        "added": len(current.keys() - previous.keys()),
        "removed": len(previous.keys() - current.keys()),
        "changed": sum(previous[k] != current[k] for k in previous.keys() & current.keys()),
        "unchanged": sum(previous[k] == current[k] for k in previous.keys() & current.keys()),
    }
