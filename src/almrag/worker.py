"""Independent COLLECT worker with durable lease renewal and liveness checks."""
import argparse
import json
import math
from pathlib import Path
import signal
import threading
import time
from uuid import uuid4

from almrag.config import Settings
from almrag.security import safe_event
from almrag.queue import LeaseLost


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


def run_once(queue, owner, collection_service=None, *, stop_check=lambda: False,
             health_path=None, lease_seconds=30, heartbeat_interval=5, processing_service=None, index_service=None, pipeline_service=None, operations_service=None, quality_service=None):
    """Claim one job; CollectionService alone owns normal terminal transitions.

    Heartbeats run independently while a connector performs network work or waits.
    Any heartbeat failure revokes this worker's permission to continue and leaves
    the persisted lease/checkpoint for recovery; no unguarded finish is attempted.
    """
    if not math.isfinite(lease_seconds) or lease_seconds <= 0:
        raise ValueError('invalid lease')
    if not math.isfinite(heartbeat_interval) or heartbeat_interval <= 0:
        raise ValueError('invalid heartbeat interval')
    interval = min(heartbeat_interval, lease_seconds / 3, 10)
    job = queue.claim(owner, lease_seconds=lease_seconds)
    if job is None:
        return False
    service = collection_service if job['stage']=='COLLECT' else processing_service if job['stage'] in {'PROCESS','EMBED'} else index_service if job['stage'] in {'INDEX','REBUILD'} else pipeline_service if job['stage'] in {'SYNC','REPLAY'} else operations_service if job['stage'] in {'EXPORT','IMPORT'} else quality_service if job['stage'] in {'INTEGRITY','EVALUATE'} else None
    if service is None:
        queue.finish(job['job_id'], job['fencing_token'], state='BLOCKED', error_code='STAGE_UNAVAILABLE')
        print(json.dumps(safe_event(action='job_blocked', outcome='blocked', job_uid=job['job_id'],
                                    stage=job['stage'], error_code='STAGE_UNAVAILABLE')), flush=True)
        return True

    finished = threading.Event()
    heartbeat_errors = []

    def abort_check():
        if heartbeat_errors:
            raise heartbeat_errors[0]
        return bool(stop_check())

    def renew():
        while not finished.wait(interval):
            try:
                queue.heartbeat(job['job_id'], job['fencing_token'], lease_seconds=lease_seconds)
                if health_path is not None:
                    write_health(health_path)
            except Exception as error:
                if isinstance(error,LeaseLost):
                    try:current=queue.get_job(job['job_id'])
                    except Exception:current=None
                    if current and current.get('retry_count')==job.get('retry_count') and current['state'] in {'SUCCEEDED','COMPLETED_WITH_ERRORS','PAUSED','BLOCKED','FAILED','CANCELLED'}:
                        finished.set()
                        return
                # Report no raw database/transport exception text to logs or API.
                heartbeat_errors.append(error if isinstance(error, LeaseLost) else LeaseLost('heartbeat unavailable'))
                return

    heartbeat = threading.Thread(target=renew, name='almrag-heartbeat-' + job['job_id'], daemon=True)
    try:
        if health_path is not None:
            write_health(health_path)
        heartbeat.start()
        try:
            service.run(job, abort_check=abort_check)
        except LeaseLost:
            raise
        except Exception:
            abort_check()  # A failed heartbeat must never become a local handler error.
            queue.finish(job['job_id'], job['fencing_token'], state='BLOCKED', error_code='WORKER_ERROR')
            print(json.dumps(safe_event(action='job_blocked', outcome='blocked', job_uid=job['job_id'],
                                        stage=job['stage'], error_code='WORKER_ERROR')), flush=True)
        abort_check()
    finally:
        finished.set()
        if heartbeat.ident is not None:
            heartbeat.join()
    return True


class _ConfiguredCollection:
    """Delay profile/credential construction until a supported job is claimed."""
    def __init__(self, db, settings):
        self.db = db
        self.settings = settings

    def _operations(self):
        if not hasattr(self,'operations'):
            from almrag.operations import OperationsService
            self.operations=OperationsService(self.db,attachment_root=self.settings.attachment_directory)
        return self.operations

    def cleanup_pending(self):
        """Retry derived-index cleanup only after job heartbeat ownership ends."""
        if hasattr(self, 'indexing'):
            try:
                self.indexing.cleanup()
            except Exception:
                print(json.dumps(safe_event(action='index_cleanup', outcome='deferred',
                                            error_code='CLEANUP_RETRY_PENDING')), flush=True)

        if self.db is not None:
            try:self._operations().maintenance()
            except Exception:
                print(json.dumps(safe_event(action='operations_maintenance',outcome='deferred',error_code='MAINTENANCE_RETRY_PENDING')),flush=True)

        if self.db is not None and self.settings.notion_summary_enabled:
            from almrag.docs_publish import SummaryOutbox,NotionSummarySender
            from almrag.connection import Connections
            try:
                resolver=lambda:Connections(self.db,self.settings).secret(self.settings.notion_auth_ref or '')
                sender=NotionSummarySender(self.settings.notion_root_page,resolver,allow_network=True)
                SummaryOutbox(self.db,send=sender,enabled=True).flush()
            except Exception:
                print(json.dumps(safe_event(action='docs_publish',outcome='deferred',error_code='PUBLISH_RETRY_PENDING')),flush=True)

    def run(self, job, abort_check):
        if job.get('stage') in {'INTEGRITY','EVALUATE'}:
            from almrag.quality import QualityService
            from almrag.retrieval import SearchService
            from almrag.model_runtime import ModelRuntimeRegistry
            from almrag.vector_runtime import VectorRuntimeRegistry
            registry=ModelRuntimeRegistry(self.settings,self.db)
            vectors=VectorRuntimeRegistry(self.settings,self.db)
            search=SearchService(self.db,registry.get,vectors)
            return QualityService(self.db,search,vectors if self.settings.live_vector_enabled else None,attachment_root=self.settings.attachment_directory).run(job,abort_check=abort_check)
        if job.get('stage') in {'EXPORT','IMPORT'}:return self._operations().run(job,abort_check)
        if job.get('stage') in {'PROCESS','EMBED','INDEX','REBUILD','SYNC','REPLAY'}:
            from almrag.processing import ProcessingService
            from almrag.model_runtime import ModelRuntimeRegistry
            if not hasattr(self,'processing'):
                self.registry=ModelRuntimeRegistry(self.settings,self.db)
                self.processing=ProcessingService(self.db,self.registry.get)
            if job['stage'] in {'INDEX','REBUILD','SYNC','REPLAY'}:
                from almrag.indexing import IndexService
                from almrag.vector_runtime import VectorRuntimeRegistry
                if not hasattr(self,'indexing'):self.indexing=IndexService(self.db,self.processing,VectorRuntimeRegistry(self.settings,self.db))
                if job['stage'] in {'INDEX','REBUILD'}:return self.indexing.run(job,abort_check=abort_check)
                from almrag.pipeline import PipelineService
                from almrag.collection import CollectionService
                from almrag.connection import Connections
                if not hasattr(self,'pipeline'):
                    connections=Connections(self.db,self.settings)
                    collection=CollectionService(self.db,connections.connector,self.settings.attachment_directory)
                    self.pipeline=PipelineService(self.db,collection,self.processing,self.indexing)
                return self.pipeline.run(job,abort_check=abort_check)
            return self.processing.run(job,abort_check=abort_check)
        from almrag.collection import CollectionService
        from almrag.connection import Connections
        connections = Connections(self.db, self.settings)
        service = CollectionService(self.db, connections.connector, self.settings.attachment_directory)
        return service.run(job, abort_check=abort_check)


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
    collection_service=_ConfiguredCollection(db,settings)
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    print(json.dumps(safe_event(action='worker_start',outcome='ok')),flush=True)
    try:
        while not stopping:
            try:
                run_once(queue,owner,collection_service,stop_check=lambda: stopping,health_path=path,processing_service=collection_service,index_service=collection_service,pipeline_service=collection_service,operations_service=collection_service,quality_service=collection_service)
            except LeaseLost:
                print(json.dumps(safe_event(action='lease_lost',outcome='aborted')),flush=True)
            collection_service.cleanup_pending()
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
