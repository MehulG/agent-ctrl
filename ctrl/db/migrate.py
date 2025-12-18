import sqlite3
from pathlib import Path

def ensure_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS _migrations (id TEXT PRIMARY KEY)")
        conn.commit()

        migration_id = "001_init"
        cur.execute("SELECT 1 FROM _migrations WHERE id = ?", (migration_id,))
        if cur.fetchone():
            return

        sql = Path("migrations/001_init.sql").read_text(encoding="utf-8")
        conn.executescript(sql)
        cur.execute("INSERT INTO _migrations (id) VALUES (?)", (migration_id,))
        conn.commit()
    finally:
        conn.close()
