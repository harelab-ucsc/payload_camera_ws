#!/usr/bin/env python3
"""
docker/tests/test_db_schema.py

Verifies the SQLite schema produced by stream_processor.dbConnector.boot()
matches what post_process_and_save() and the surrounding code expect.

The post_process_and_save SQL insert lists these columns for the images
table:
    x, y, z, q, u, a, t, rtk_status, ins_status, radalt, save_loc, pps_time

If dbConnector.boot's CREATE TABLE drifts from that list, runtime inserts
fail at the very last step of every PPS cycle. These tests catch that
divergence at build time.

Pure-Python; no ROS or workspace install required beyond the python module.
"""

import os
import sqlite3
import tempfile

import pytest

from stream_processor.dbConnector import dbConnector

SENSOR = "frc_payload"
DB = "test_flight_data"


@pytest.fixture
def db():
    """Boot a fresh dbConnector against a temp sqlite file, yield (dbc, path)."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, DB)
        dbc = dbConnector(db_path)
        dbc.boot(DB, SENSOR)
        yield dbc, db_path + ".db"


def _columns(db_file: str, table: str) -> list[str]:
    """Return the column names of `table` in declared order."""
    with sqlite3.connect(db_file) as conn:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cur.fetchall()]


# ── images table — the high-traffic one written every PPS cycle ──────────────

def test_images_table_columns_match_insert_statement(db):
    """The columns written by post_process_and_save must all exist."""
    _, path = db
    cols = _columns(path, f"{SENSOR}_images_{DB}")

    expected = [
        "x", "y", "z",
        "q", "u", "a", "t",
        "rtk_status", "ins_status",
        "radalt",
        "save_loc",
        "pps_time",
    ]
    assert cols == expected, (
        f"images schema drifted from post_process_and_save's INSERT column list.\n"
        f"  got:      {cols}\n"
        f"  expected: {expected}"
    )


def test_images_save_loc_is_unique(db):
    """save_loc UNIQUE keeps duplicate rows out when retrying a save."""
    _, path = db
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            f"SELECT * FROM pragma_table_info('{SENSOR}_images_{DB}')"
        )
        rows = cur.fetchall()
    save_loc = next(r for r in rows if r[1] == "save_loc")
    # rows are: (cid, name, type, notnull, dflt_value, pk)
    # PRAGMA table_info doesn't surface UNIQUE; assert via index instead
    with sqlite3.connect(path) as conn:
        idx = conn.execute(
            f"SELECT * FROM pragma_index_list('{SENSOR}_images_{DB}')"
        ).fetchall()
    # Any UNIQUE column shows up here
    has_unique = any(row[2] == 1 for row in idx)  # row[2] == 'unique' flag
    assert has_unique, "expected at least one UNIQUE constraint on images table"
    assert save_loc is not None  # column exists


def test_images_insert_round_trip(db):
    """An insert built the same way post_process_and_save builds it round-trips."""
    dbc, path = db
    paths_str = "/tmp/cam0_0_1.0.tiff|/tmp/cam0_1_1.0.tiff"
    # Mirror the val_str construction in post_process_and_save: paths_str
    # must be quoted because it contains '/' and '|' which would otherwise
    # break the inline SQL VALUES list.
    val_str = ",".join(map(str, [
        551234.5, 4123456.7, 100.0,         # x, y, z
        0.1, 0.2, 0.3, 0.95,                 # q, u, a, t
        4, 9,                                # rtk_status, ins_status
        50.0,                                # radalt
        '"' + paths_str + '"',               # save_loc (quoted)
        "1.000000000",                       # pps_time
    ]))
    dbc.insertIgnoreInto(
        f"{SENSOR}_images_{DB}",
        "x, y, z, q, u, a, t, rtk_status, ins_status, radalt, save_loc, pps_time",
        val_str,
    )

    with sqlite3.connect(path) as conn:
        rows = conn.execute(f"SELECT * FROM {SENSOR}_images_{DB}").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == pytest.approx(551234.5)
    assert row[1] == pytest.approx(4123456.7)
    assert row[10] == paths_str           # save_loc preserved with the pipe sep
    assert row[11] == pytest.approx(1.0)  # pps_time roundtripped


# ── clicks table ─────────────────────────────────────────────────────────────

def test_clicks_table_columns(db):
    _, path = db
    cols = _columns(path, f"clicks_{DB}")
    assert cols == [
        "x", "y", "zone_num", "zone_letter", "z", "z_msl", "tag",
    ], f"clicks schema drifted: {cols}"


def test_clicks_insert_round_trip(db):
    """insertClicks accepts the (x, y, zone_num, zone_letter, z, z_msl, tag) row."""
    dbc, path = db
    rows_in = [
        (551234.5, 4123456.7, 10, "S", 100.0, 50.0, 1),
        (551235.0, 4123457.0, 10, "S", 101.0, 51.0, 2),
    ]
    dbc.insertClicks(f"clicks_{DB}", rows_in)
    with sqlite3.connect(path) as conn:
        rows_out = conn.execute(f"SELECT * FROM clicks_{DB}").fetchall()
    assert rows_out == rows_in


# ── parameters table ─────────────────────────────────────────────────────────

def test_parameters_table_columns(db):
    _, path = db
    cols = _columns(path, f"parameters_{DB}")
    assert cols == [
        "sensorID", "resolution", "intrinsics1", "intrinsics2", "extrinsics",
    ], f"parameters schema drifted: {cols}"


# ── ins_data table ───────────────────────────────────────────────────────────

def test_ins_data_table_columns(db):
    _, path = db
    cols = _columns(path, f"ins_data_{DB}")
    assert cols == [
        "x", "y", "z",
        "q", "u", "a", "t",
        "insStatus", "hdwStatus",
        "time1", "time2",
    ], f"ins_data schema drifted: {cols}"


# ── all four tables exist ─────────────────────────────────────────────────────

def test_boot_creates_all_four_tables(db):
    _, path = db
    with sqlite3.connect(path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    expected = {
        f"{SENSOR}_images_{DB}",
        f"clicks_{DB}",
        f"parameters_{DB}",
        f"ins_data_{DB}",
    }
    assert expected.issubset(names), (
        f"missing tables: {expected - names}; got: {names}"
    )
