"""Independent worker shell; real ALM stage handlers arrive in M2+."""
import argparse
import json
import os
from pathlib import Path
import signal
import time
from uuid import uuid4

from almrag.config import Settings
from almrag.security import safe_event


def write_health(path, now=None):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'timestamp':time.time() if now is None else now}))
    temporary.replace(path)


def healthy(path, now=None):
    try:
        stamp=json.loads(Path(path).read_text())['timestamp']
        age=(time.time() if now is None else now)-stamp
        return 0<=age<30
    except (OSError,ValueError,KeyError,TypeError):
        return False


def run_once(queue, owner):
    job=queue.claim(owner,lease_seconds=30)
    if job is None:
        return False
    queue.finish(job['job_id'],job['fencing_token'],state='BLOCKED',error_code='STAGE_UNAVAILABLE')
    print(json.dumps(safe_event(action='job_blocked',outcome='blocked',job_uid=job['job_id'],stage=job['stage'],error_code='STAGE_UNAVAILABLE')),flush=True)
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--health',action='store_true')
    args=parser.parse_args()
    settings=Settings.from_env()
    path=Path(settings.database_path).parent/'worker-health.json'
    if args.health:
        return 0 if healthy(path) else 1
    from almrag.storage import Database
    from almrag.queue import Queue
    db=Database(settings.database_path)
    db.migrate()
    queue=Queue(db)
    owner=str(uuid4())
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    print(json.dumps(safe_event(action='worker_start',outcome='ok')),flush=True)
    try:
        while not stopping:
            run_once(queue,owner)
            write_health(path)
            if args.once:
                break
            time.sleep(1)
    finally:
        path.unlink(missing_ok=True)
        print(json.dumps(safe_event(action='worker_stop',outcome='ok')),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
