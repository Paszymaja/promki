import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# All timestamps in this DB are written via _utc_now_iso() so that lexical
# sort of the TEXT column matches chronological order. Do not bypass it.
_SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at   TEXT    NOT NULL UNIQUE,
    coupon_count INTEGER NOT NULL CHECK (coupon_count >= 0)
);

CREATE TABLE IF NOT EXISTS coupon_observations (
    run_id               INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    coupon_id            TEXT    NOT NULL,
    title                TEXT    NOT NULL DEFAULT '',
    discount_title       TEXT    NOT NULL DEFAULT '',
    discount_description TEXT    NOT NULL DEFAULT '',
    valid_start          TEXT    NOT NULL DEFAULT '',
    valid_end            TEXT    NOT NULL DEFAULT '',
    is_activated         INTEGER NOT NULL CHECK (is_activated IN (0, 1)),
    raw_json             TEXT    NOT NULL CHECK (json_valid(raw_json)),
    source               TEXT    NOT NULL DEFAULT 'lidl',
    PRIMARY KEY (run_id, coupon_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_obs_coupon_id ON coupon_observations (coupon_id);
"""

_DIFF_FIELDS = ("title", "discount_title", "discount_description", "valid_end", "is_activated")


class SchemaVersionError(Exception):
    """Raised when the on-disk schema version does not match the code's expectation."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_schema(conn, db_path)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection, db_path: Path) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == _SCHEMA_VERSION:
        return
    if version == 0:
        # Pre-versioned DB might be the old `snapshots` table from before this rewrite.
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='snapshots'"
        ).fetchone():
            raise SchemaVersionError(
                f"Found legacy 'snapshots' table at {db_path}. "
                f"Delete the file and re-run to recreate with the current schema."
            )
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        return
    if version == 1:
        _migrate_v1_to_v2(conn, db_path)
        return
    raise SchemaVersionError(
        f"Database schema version is {version}, expected {_SCHEMA_VERSION}. "
        f"Delete {db_path} and re-run to recreate."
    )


def _migrate_v1_to_v2(conn: sqlite3.Connection, db_path: Path) -> None:
    try:
        conn.execute("ALTER TABLE coupon_observations ADD COLUMN source TEXT NOT NULL DEFAULT 'lidl'")
    except sqlite3.OperationalError:
        pass
    conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")


def _to_row(run_id: int, coupon: dict, source: str = "lidl") -> tuple:
    discount = coupon.get("discount") if isinstance(coupon.get("discount"), dict) else {}
    validity = coupon.get("validity") if isinstance(coupon.get("validity"), dict) else {}
    return (
        run_id,
        coupon.get("id") or "",
        coupon.get("title") or "",
        discount.get("title") or "",
        discount.get("description") or "",
        validity.get("start") or "",
        validity.get("end") or "",
        1 if coupon.get("isActivated") else 0,
        json.dumps(coupon, ensure_ascii=False),
        source,
    )


def save_snapshot(
    db_path: Path,
    coupons: list[dict],
    *,
    fetched_at: str | None = None,
    source: str = "lidl",
) -> str:
    """Record a fetch in `runs` and one row per coupon in `coupon_observations`.

    Always records the run, even when `coupons` is empty — that captures
    "we ran but the store had nothing." Returns the timestamp used.
    """
    if fetched_at is None:
        fetched_at = _utc_now_iso()
    valid_coupons = [c for c in coupons if c.get("id")]

    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO runs (fetched_at, coupon_count) VALUES (?, ?)",
            (fetched_at, len(valid_coupons)),
        )
        run_id = cursor.lastrowid
        if valid_coupons:
            conn.executemany(
                """
                INSERT OR IGNORE INTO coupon_observations (
                    run_id, coupon_id, title, discount_title, discount_description,
                    valid_start, valid_end, is_activated, raw_json, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [_to_row(run_id, c, source) for c in valid_coupons],
            )
    return fetched_at


def list_snapshots(db_path: Path) -> list[str]:
    if not db_path.exists():
        return []
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT fetched_at FROM runs ORDER BY fetched_at DESC"
        ).fetchall()
    return [r["fetched_at"] for r in rows]


def diff_latest(db_path: Path, *, source: str | None = None) -> dict | None:
    """Compare the two most recent runs for the given `source` (or all if None)."""
    snapshots = list_snapshots(db_path)
    if len(snapshots) < 2:
        return None

    query = """
        SELECT o.* FROM coupon_observations o
        JOIN runs r ON o.run_id = r.id
        WHERE r.fetched_at = ?
    """
    source_filter = " AND o.source = ?"
    params_latest = (snapshots[0],)
    params_prev = (snapshots[1],)

    if source is not None:
        query += source_filter
        params_latest += (source,)
        params_prev += (source,)

    with _connect(db_path) as conn:
        latest_rows = {r["coupon_id"]: dict(r) for r in conn.execute(query, params_latest)}
        prev_rows = {r["coupon_id"]: dict(r) for r in conn.execute(query, params_prev)}

    added = [latest_rows[cid] for cid in latest_rows if cid not in prev_rows]
    removed = [prev_rows[cid] for cid in prev_rows if cid not in latest_rows]
    changed = []
    for cid, latest_row in latest_rows.items():
        prev_row = prev_rows.get(cid)
        if prev_row is None:
            continue
        diffs = {f: (prev_row[f], latest_row[f]) for f in _DIFF_FIELDS if prev_row[f] != latest_row[f]}
        if diffs:
            changed.append({"coupon_id": cid, "title": latest_row["title"], "diffs": diffs})

    return {
        "latest": snapshots[0],
        "previous": snapshots[1],
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def format_diff(diff: dict | None) -> list[str]:
    if diff is None:
        return ["No previous snapshot to compare — this is the first run."]
    if not diff["added"] and not diff["removed"] and not diff["changed"]:
        return [f"No changes since {diff['previous']}."]

    lines = [f"Changes since {diff['previous']}:"]
    if diff["added"]:
        lines.append(f"  + Added ({len(diff['added'])}):")
        lines.extend(f"      {row['title']}" for row in diff["added"])
    if diff["removed"]:
        lines.append(f"  - Removed ({len(diff['removed'])}):")
        lines.extend(f"      {row['title']}" for row in diff["removed"])
    if diff["changed"]:
        lines.append(f"  ~ Changed ({len(diff['changed'])}):")
        for entry in diff["changed"]:
            lines.append(f"      {entry['title']}")
            for field, (old, new) in entry["diffs"].items():
                lines.append(f"        {field}: {old!r} -> {new!r}")
    return lines


def print_diff(diff: dict | None) -> None:
    print()
    for line in format_diff(diff):
        print(line)
