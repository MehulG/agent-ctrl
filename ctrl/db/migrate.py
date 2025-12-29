import sqlite3
from pathlib import Path

def ensure_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS _migrations (id TEXT PRIMARY KEY)")
        conn.commit()

        cur.execute("SELECT id FROM _migrations")
        applied = {row[0] for row in cur.fetchall()}

        migrations = [
            ("001_init", "migrations/001_init.sql"),
            ("002_add_risk_and_approval", "migrations/002_add_risk_and_approval.sql"),
        ]

        for migration_id, path in migrations:
            if migration_id in applied:
                continue
            sql = Path(path).read_text(encoding="utf-8")
            conn.executescript(sql)
            cur.execute("INSERT INTO _migrations (id) VALUES (?)", (migration_id,))
            conn.commit()
    finally:
        conn.close()
