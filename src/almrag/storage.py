"""Transactional SQLite foundation. No source transport or publication handler."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import uuid


def canonical_uid(*parts):
    """Preserve ordered source components without delimiter ambiguity."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(parts,ensure_ascii=False,separators=(',',':'))))


class Database:
    def __init__(self,path):
        self.path=Path(path)

    @contextmanager
    def connect(self):
        c=sqlite3.connect(str(self.path),timeout=30,isolation_level=None)
        c.row_factory=sqlite3.Row
        try:
            c.execute('PRAGMA foreign_keys=ON')
            c.execute('PRAGMA recursive_triggers=ON')
            c.execute('PRAGMA busy_timeout=30000')
            c.execute('PRAGMA journal_mode=WAL')
            yield c
        finally:
            c.close()

    @contextmanager
    def transaction(self):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    def migrate(self):
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.path.touch(mode=0o600,exist_ok=True)
        with self.transaction() as c:
            c.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY)')
            if c.execute('SELECT 1 FROM schema_migrations WHERE version=1').fetchone():
                return
            # executescript commits implicitly; execute complete statements individually.
            buffer=''
            for line in (Path(__file__).parent/'migrations'/'001_initial.sql').read_text().splitlines(True):
                buffer+=line
                if sqlite3.complete_statement(buffer):
                    c.execute(buffer)
                    buffer=''
            if buffer.strip():
                raise ValueError('incomplete migration')
            c.execute('INSERT INTO schema_migrations VALUES(1)')

    def add_instance(self,source_type,base_url,display_name,auth_ref):
        with self.transaction() as c:
            existing=c.execute('SELECT instance_uid FROM instances WHERE source_type=? AND base_url=?',(source_type,base_url)).fetchone()
            if existing:
                return existing['instance_uid']
            uid=str(uuid.uuid4())
            c.execute('INSERT INTO instances(instance_uid,source_type,base_url,display_name,auth_ref) VALUES(?,?,?,?,?)',(uid,source_type,base_url,display_name,auth_ref))
        return uid

    def add_project(self,instance_uid,source_project_id,name):
        uid=canonical_uid('project',instance_uid,source_project_id)
        with self.transaction() as c:
            c.execute('INSERT INTO projects(project_uid,instance_uid,source_project_id,name) VALUES(?,?,?,?) ON CONFLICT(project_uid) DO NOTHING',(uid,instance_uid,source_project_id,name))
        return uid
