"""Cross-process read snapshots protect retired generations until readers finish."""
from contextlib import contextmanager
from pathlib import Path
import time
from uuid import uuid4

from almrag.alm_http import _SlotLock


class ReaderError(ValueError):
    def __init__(self,code):
        super().__init__(code);self.code=code


class ReaderRegistry:
    def __init__(self,db):
        self.db=db
        path=Path(db.path).resolve()
        self.root=path.parent/('.'+path.name+'.search-locks')
        self.root.mkdir(mode=0o700,exist_ok=True)

    @staticmethod
    def _pairs(c,projects):
        pairs={}
        for project in projects:
            row=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(project,)).fetchone()
            if row is None:raise ReaderError('PROJECT_NOT_FOUND')
            if row[0] is not None:pairs[project]=row[0]
        return pairs

    def _release(self,reader):
        with self.db.transaction() as c:c.execute('DELETE FROM search_reader_pins WHERE reader_uid=?',(reader,))

    @contextmanager
    def snapshot(self,project_uids,*,on_pinned=lambda:None):
        if not project_uids or len(set(project_uids))!=len(project_uids):raise ReaderError('INVALID_PROJECTS')
        reader=str(uuid4());lock=_SlotLock(self.root/reader)
        try:
            if not lock.acquire():raise ReaderError('READER_LOCK_UNAVAILABLE')
            for _ in range(3):
                with self.db.transaction() as c:
                    pairs=self._pairs(c,project_uids)
                    c.executemany('INSERT INTO search_reader_pins VALUES(?,?,?,?)',[(reader,p,g,time.time()) for p,g in pairs.items()])
                on_pinned()
                with self.db.connect() as c:
                    c.execute('BEGIN')
                    try:
                        if self._pairs(c,project_uids)==pairs:
                            yield c,pairs
                            return
                    finally:c.rollback()
                self._release(reader)
            raise ReaderError('SEARCH_SNAPSHOT_CHANGED')
        finally:
            try:self._release(reader)
            finally:lock.close()

    def has_readers(self,c,generation_uid):
        readers=c.execute('SELECT reader_uid FROM search_reader_pins WHERE generation_uid=?',(generation_uid,)).fetchall()
        for row in readers:
            lock=_SlotLock(self.root/row[0])
            try:
                if not lock.acquire():return True
                c.execute('DELETE FROM search_reader_pins WHERE reader_uid=?',(row[0],))
            finally:lock.close()
        return False
