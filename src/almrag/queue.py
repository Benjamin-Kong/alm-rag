"""Global FIFO with SQLite write locking, durable checkpoints and lease fencing."""
import json
import re
import time
import uuid


class LeaseLost(ValueError):
    pass


class Queue:
    def __init__(self,db):
        self.db=db

    @staticmethod
    def _row(row):
        if row is None: return None
        result=dict(row)
        result['checkpoint']=json.loads(result['checkpoint'])
        return result

    def get_job(self,job_id):
        with self.db.connect() as c:
            return self._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone())

    def enqueue(self,project_uid,stage):
        if not isinstance(stage,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',stage):
            raise ValueError('invalid stage')
        job_id=str(uuid.uuid4()); now=time.time()
        with self.db.transaction() as c:
            c.execute('INSERT INTO jobs(job_id,project_uid,stage,created_at,updated_at) VALUES(?,?,?,?,?)',(job_id,project_uid,stage,now,now))
            self._event(c,job_id,'QUEUED',now)
            return self._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone())

    @staticmethod
    def _event(c,job_id,state,now,error_code=None):
        c.execute('INSERT INTO job_events(job_id,occurred_at,state,error_code) VALUES(?,?,?,?)',(job_id,now,state,error_code))

    def recover_expired(self):
        with self.db.transaction() as c:
            return self._recover(c,time.time())

    def _recover(self,c,now):
        rows=c.execute("SELECT job_id FROM jobs WHERE state='RUNNING' AND lease_expires_at<=?",(now,)).fetchall()
        for r in rows:
            c.execute("UPDATE jobs SET state='QUEUED',owner=NULL,fencing_token=NULL,lease_expires_at=NULL,retry_count=retry_count+1,updated_at=? WHERE job_id=?",(now,r['job_id']))
            self._event(c,r['job_id'],'QUEUED',now,'LEASE_EXPIRED')
        return len(rows)

    def claim(self,owner,lease_seconds=30):
        if not owner or lease_seconds<=0: raise ValueError('invalid lease')
        with self.db.transaction() as c:
            now=time.time(); self._recover(c,now)
            if c.execute("SELECT 1 FROM jobs WHERE state='RUNNING'").fetchone(): return None
            row=c.execute("SELECT job_id FROM jobs WHERE state='QUEUED' ORDER BY sequence LIMIT 1").fetchone()
            if row is None: return None
            job_id=row['job_id']
            c.execute("UPDATE jobs SET state='RUNNING',owner=?,fencing_token=?,lease_expires_at=?,updated_at=? WHERE job_id=?",(owner,str(uuid.uuid4()),now+lease_seconds,now,job_id))
            self._event(c,job_id,'RUNNING',now)
            return self._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone())

    @staticmethod
    def _guard(c,job_id,token,now):
        if not c.execute("SELECT 1 FROM jobs WHERE job_id=? AND fencing_token=? AND state='RUNNING' AND lease_expires_at>?",(job_id,token,now)).fetchone():
            raise LeaseLost('lease expired or replaced')

    def checkpoint(self,job_id,token,payload):
        encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False)
        with self.db.transaction() as c:
            now=time.time(); self._guard(c,job_id,token,now)
            c.execute('UPDATE jobs SET checkpoint=?,updated_at=? WHERE job_id=?',(encoded,now,job_id))

    def heartbeat(self,job_id,token,lease_seconds=30):
        if lease_seconds<=0: raise ValueError('invalid lease')
        with self.db.transaction() as c:
            now=time.time(); self._guard(c,job_id,token,now)
            c.execute('UPDATE jobs SET lease_expires_at=?,updated_at=? WHERE job_id=?',(now+lease_seconds,now,job_id))

    def request_pause(self,job_id):
        """QUEUED jobs pause at once; RUNNING jobs stop cooperatively at the worker's next abort check."""
        with self.db.transaction() as c:
            now=time.time()
            row=c.execute('SELECT state FROM jobs WHERE job_id=?',(job_id,)).fetchone()
            if row is None: return None
            if row['state']=='QUEUED':
                c.execute("UPDATE jobs SET state='PAUSED',last_error_code='ABORT_REQUESTED',updated_at=? WHERE job_id=?",(now,job_id))
                self._event(c,job_id,'PAUSED',now,'ABORT_REQUESTED')
            elif row['state']=='RUNNING':
                c.execute('UPDATE jobs SET pause_requested=1,updated_at=? WHERE job_id=?',(now,job_id))
            else: return self._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone())|{'rejected':True}
            return self._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone())

    def pause_requested(self,job_id):
        with self.db.connect() as c:
            row=c.execute('SELECT pause_requested FROM jobs WHERE job_id=?',(job_id,)).fetchone()
        return bool(row and row['pause_requested'])

    def finish(self,job_id,token,state='SUCCEEDED',error_code=None):
        if state not in {'SUCCEEDED','COMPLETED_WITH_ERRORS','PAUSED','BLOCKED','FAILED','CANCELLED'}:
            raise ValueError('invalid terminal state')
        if error_code is not None and not re.fullmatch('[A-Z][A-Z0-9_]{0,63}',error_code):
            raise ValueError('invalid error code')
        with self.db.transaction() as c:
            now=time.time(); self._guard(c,job_id,token,now)
            c.execute('UPDATE jobs SET state=?,last_error_code=?,pause_requested=0,owner=NULL,fencing_token=NULL,lease_expires_at=NULL,updated_at=? WHERE job_id=?',(state,error_code,now,job_id))
            self._event(c,job_id,state,now,error_code)
