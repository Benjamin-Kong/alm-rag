"""SRS-001/053/055: additive migration, no rewrite of M1 data."""
import sqlite3
from pathlib import Path
from almrag.storage import Database


def test_existing_v1_gets_pending_additive_migrations(tmp_path):
    path=tmp_path/'legacy.sqlite'
    with sqlite3.connect(path) as c:
        c.executescript((Path(__file__).resolve().parents[1]/'src/almrag/migrations/001_initial.sql').read_text())
        c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)')
        c.execute('INSERT INTO schema_migrations VALUES(1)')
        c.execute("INSERT INTO instances(instance_uid,source_type,base_url,display_name,auth_ref) VALUES('old','codebeamer','https://old.example.invalid','fixture','ref')")
    db=Database(path);db.migrate();db.migrate()
    with db.connect() as c:
        assert c.execute("SELECT count(*) FROM instances WHERE instance_uid='old'").fetchone()[0]==1
        assert c.execute("SELECT 1 FROM sqlite_master WHERE name='server_budgets'").fetchone()
        assert c.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]>=3
