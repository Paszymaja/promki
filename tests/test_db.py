import json
import sqlite3

import pytest

from lidl_recipe.db import (
    SchemaVersionError,
    diff_latest,
    format_diff,
    list_snapshots,
    save_snapshot,
)


def _coupon(cid, title, **overrides):
    base = {
        "id": cid,
        "title": title,
        "isActivated": False,
        "discount": {"title": "1.99 zł", "description": "regular 3.49"},
        "validity": {"start": "2026-05-01T00:00:00Z", "end": "2026-05-08T23:59:59Z"},
    }
    base.update(overrides)
    return base


T1 = "2026-05-08T10:00:00+00:00"
T2 = "2026-05-08T11:00:00+00:00"
T3 = "2026-05-08T12:00:00+00:00"


# --- save_snapshot: happy path ---


def test_save_snapshot_persists_run_and_observations(tmp_path):
    db = tmp_path / "coupons.db"
    coupons = [_coupon("a", "Ser"), _coupon("b", "Mleko")]

    fetched_at = save_snapshot(db, coupons, fetched_at=T1)

    assert fetched_at == T1
    with sqlite3.connect(db) as conn:
        runs = conn.execute("SELECT fetched_at, coupon_count FROM runs").fetchall()
        obs = conn.execute("SELECT coupon_id, title FROM coupon_observations").fetchall()
    assert runs == [(T1, 2)]
    assert sorted(obs) == [("a", "Ser"), ("b", "Mleko")]


def test_save_snapshot_creates_parent_directory(tmp_path):
    db = tmp_path / "nested" / "dir" / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
    assert db.exists()


def test_save_snapshot_default_timestamp_is_utc_iso(tmp_path):
    db = tmp_path / "coupons.db"
    fetched_at = save_snapshot(db, [_coupon("a", "Ser")])
    # Convention: every timestamp ends with the explicit UTC offset.
    assert fetched_at.endswith("+00:00")


# --- save_snapshot: empty / missing data ---


def test_empty_fetch_records_run_with_zero_count(tmp_path):
    """Empty fetches must still appear in history — that's the whole point of the runs table."""
    db = tmp_path / "coupons.db"
    fetched_at = save_snapshot(db, [], fetched_at=T1)

    assert fetched_at == T1
    with sqlite3.connect(db) as conn:
        runs = conn.execute("SELECT fetched_at, coupon_count FROM runs").fetchall()
        obs_count = conn.execute("SELECT COUNT(*) FROM coupon_observations").fetchone()[0]
    assert runs == [(T1, 0)]
    assert obs_count == 0


def test_run_recorded_when_all_coupons_lack_id(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [{"title": "no id"}, {}], fetched_at=T1)

    with sqlite3.connect(db) as conn:
        run_count = conn.execute("SELECT coupon_count FROM runs").fetchone()[0]
        obs_count = conn.execute("SELECT COUNT(*) FROM coupon_observations").fetchone()[0]
    assert run_count == 0
    assert obs_count == 0


def test_save_snapshot_skips_coupons_with_empty_string_id(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser"), _coupon("", "No ID")], fetched_at=T1)

    with sqlite3.connect(db) as conn:
        ids = [r[0] for r in conn.execute("SELECT coupon_id FROM coupon_observations")]
    assert ids == ["a"]


def test_save_snapshot_handles_duplicate_coupon_ids_in_one_run(tmp_path):
    db = tmp_path / "coupons.db"
    coupons = [_coupon("a", "First"), _coupon("a", "Second")]

    save_snapshot(db, coupons, fetched_at=T1)

    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT coupon_id, title FROM coupon_observations").fetchall()
    assert rows == [("a", "First")]  # INSERT OR IGNORE keeps the first


def test_save_snapshot_handles_explicit_none_fields(tmp_path):
    db = tmp_path / "coupons.db"
    coupon = {
        "id": "a",
        "title": None,
        "discount": {"title": None, "description": None},
        "validity": {"start": None, "end": None},
        "isActivated": None,
    }

    save_snapshot(db, [coupon], fetched_at=T1)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT title, discount_title, valid_end, is_activated FROM coupon_observations"
        ).fetchone()
    assert row == ("", "", "", 0)


def test_save_snapshot_handles_non_dict_discount_and_validity(tmp_path):
    db = tmp_path / "coupons.db"
    coupon = {"id": "a", "title": "Odd", "discount": None, "validity": "bogus"}

    save_snapshot(db, [coupon], fetched_at=T1)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT discount_title, valid_end FROM coupon_observations"
        ).fetchone()
    assert row == ("", "")


def test_save_snapshot_preserves_non_ascii(tmp_path):
    db = tmp_path / "coupons.db"
    coupon = _coupon("a", "Mąka żytnia z piątku")
    save_snapshot(db, [coupon], fetched_at=T1)

    with sqlite3.connect(db) as conn:
        title, raw = conn.execute(
            "SELECT title, raw_json FROM coupon_observations"
        ).fetchone()
    assert title == "Mąka żytnia z piątku"
    assert json.loads(raw)["title"] == "Mąka żytnia z piątku"
    assert "\\u" not in raw  # ensure_ascii=False preserves UTF-8


def test_save_snapshot_persists_full_raw_json(tmp_path):
    db = tmp_path / "coupons.db"
    coupon = _coupon("a", "Ser", custom_field="preserved", nested={"x": [1, 2]})

    save_snapshot(db, [coupon], fetched_at=T1)

    with sqlite3.connect(db) as conn:
        raw = conn.execute("SELECT raw_json FROM coupon_observations").fetchone()[0]
    parsed = json.loads(raw)
    assert parsed["custom_field"] == "preserved"
    assert parsed["nested"] == {"x": [1, 2]}


# --- save_snapshot: schema constraint enforcement ---


def test_unique_constraint_on_fetched_at(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
    with pytest.raises(sqlite3.IntegrityError):
        save_snapshot(db, [_coupon("b", "Mleko")], fetched_at=T1)


def test_check_constraint_rejects_invalid_is_activated(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        run_id = conn.execute("SELECT id FROM runs").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO coupon_observations "
                "(run_id, coupon_id, is_activated, raw_json) VALUES (?, ?, ?, ?)",
                (run_id, "bad", 2, "{}"),
            )


def test_check_constraint_rejects_invalid_json(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        run_id = conn.execute("SELECT id FROM runs").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO coupon_observations "
                "(run_id, coupon_id, is_activated, raw_json) VALUES (?, ?, ?, ?)",
                (run_id, "bad", 0, "not json at all"),
            )


def test_foreign_key_on_delete_cascade(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser"), _coupon("b", "Mleko")], fetched_at=T1)

    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM runs WHERE fetched_at = ?", (T1,))
        conn.commit()
        obs_count = conn.execute("SELECT COUNT(*) FROM coupon_observations").fetchone()[0]
    assert obs_count == 0


# --- list_snapshots ---


def test_list_snapshots_empty_when_db_missing(tmp_path):
    assert list_snapshots(tmp_path / "missing.db") == []


def test_list_snapshots_orders_newest_first(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T2)

    assert list_snapshots(db) == [T2, T1]


def test_list_snapshots_includes_empty_runs(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
    save_snapshot(db, [], fetched_at=T2)
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T3)

    assert list_snapshots(db) == [T3, T2, T1]


# --- diff_latest ---


def test_diff_latest_none_when_no_snapshots(tmp_path):
    assert diff_latest(tmp_path / "missing.db") is None


def test_diff_latest_none_when_only_one_snapshot(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
    assert diff_latest(db) is None


def test_diff_latest_detects_added(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
    save_snapshot(db, [_coupon("a", "Ser"), _coupon("b", "Mleko")], fetched_at=T2)

    diff = diff_latest(db)
    assert [r["coupon_id"] for r in diff["added"]] == ["b"]
    assert diff["removed"] == []
    assert diff["changed"] == []


def test_diff_latest_detects_removed(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser"), _coupon("b", "Mleko")], fetched_at=T1)
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T2)

    diff = diff_latest(db)
    assert [r["coupon_id"] for r in diff["removed"]] == ["b"]


def test_diff_latest_detects_discount_change(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(
        db,
        [_coupon("a", "Ser", discount={"title": "1.99 zł", "description": ""})],
        fetched_at=T1,
    )
    save_snapshot(
        db,
        [_coupon("a", "Ser", discount={"title": "1.49 zł", "description": ""})],
        fetched_at=T2,
    )

    diff = diff_latest(db)
    assert len(diff["changed"]) == 1
    assert diff["changed"][0]["diffs"]["discount_title"] == ("1.99 zł", "1.49 zł")


def test_diff_latest_detects_activation_change(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser", isActivated=False)], fetched_at=T1)
    save_snapshot(db, [_coupon("a", "Ser", isActivated=True)], fetched_at=T2)

    diff = diff_latest(db)
    assert diff["changed"][0]["diffs"]["is_activated"] == (0, 1)


def test_diff_latest_ignores_valid_start_changes(tmp_path):
    """valid_start is intentionally not in _DIFF_FIELDS — document that."""
    db = tmp_path / "coupons.db"
    save_snapshot(
        db,
        [_coupon("a", "Ser", validity={"start": "2026-01-01T00:00:00Z", "end": "2026-05-08T23:59:59Z"})],
        fetched_at=T1,
    )
    save_snapshot(
        db,
        [_coupon("a", "Ser", validity={"start": "2026-02-01T00:00:00Z", "end": "2026-05-08T23:59:59Z"})],
        fetched_at=T2,
    )

    diff = diff_latest(db)
    assert diff["changed"] == []


def test_diff_latest_no_changes_between_identical_snapshots(tmp_path):
    db = tmp_path / "coupons.db"
    coupons = [_coupon("a", "Ser"), _coupon("b", "Mleko")]
    save_snapshot(db, coupons, fetched_at=T1)
    save_snapshot(db, coupons, fetched_at=T2)

    diff = diff_latest(db)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["changed"] == []


def test_diff_latest_uses_two_most_recent_only(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Old")], fetched_at="2026-05-01T00:00:00+00:00")
    save_snapshot(db, [_coupon("a", "Middle")], fetched_at="2026-05-02T00:00:00+00:00")
    save_snapshot(db, [_coupon("a", "Latest")], fetched_at="2026-05-03T00:00:00+00:00")

    diff = diff_latest(db)
    assert diff["latest"] == "2026-05-03T00:00:00+00:00"
    assert diff["previous"] == "2026-05-02T00:00:00+00:00"
    assert diff["changed"][0]["diffs"]["title"] == ("Middle", "Latest")


def test_diff_latest_when_previous_run_was_empty(tmp_path):
    """If the previous run had no coupons, every coupon today is 'added'."""
    db = tmp_path / "coupons.db"
    save_snapshot(db, [], fetched_at=T1)
    save_snapshot(db, [_coupon("a", "Ser"), _coupon("b", "Mleko")], fetched_at=T2)

    diff = diff_latest(db)
    assert {r["coupon_id"] for r in diff["added"]} == {"a", "b"}
    assert diff["removed"] == []
    assert diff["changed"] == []


# --- format_diff ---


def test_format_diff_first_run():
    lines = format_diff(None)
    assert any("first run" in line for line in lines)


def test_format_diff_no_changes():
    diff = {"latest": T2, "previous": T1, "added": [], "removed": [], "changed": []}
    assert format_diff(diff) == [f"No changes since {T1}."]


def test_format_diff_includes_added_removed_changed():
    diff = {
        "latest": T2,
        "previous": T1,
        "added": [{"title": "New Item"}],
        "removed": [{"title": "Old Item"}],
        "changed": [{
            "coupon_id": "a",
            "title": "Changed Item",
            "diffs": {"discount_title": ("1.99 zł", "1.49 zł")},
        }],
    }
    output = "\n".join(format_diff(diff))
    assert "New Item" in output
    assert "Old Item" in output
    assert "Changed Item" in output
    assert "1.99 zł" in output and "1.49 zł" in output


# --- schema versioning ---


def test_legacy_snapshots_table_raises_schema_version_error(tmp_path):
    db = tmp_path / "coupons.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE snapshots (id TEXT)")
        conn.commit()

    with pytest.raises(SchemaVersionError, match="legacy"):
        save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)


def test_future_schema_version_raises(tmp_path):
    db = tmp_path / "coupons.db"
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA user_version = 99")
        conn.commit()

    with pytest.raises(SchemaVersionError, match="version is 99"):
        save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)


def test_user_version_set_after_initialization(tmp_path):
    db = tmp_path / "coupons.db"
    save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)

    with sqlite3.connect(db) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1


# --- error surfaces ---


def test_save_snapshot_propagates_sqlite_errors(tmp_path):
    db = tmp_path / "coupons.db"
    db.write_bytes(b"this is not a sqlite database file")

    with pytest.raises(sqlite3.DatabaseError):
        save_snapshot(db, [_coupon("a", "Ser")], fetched_at=T1)
