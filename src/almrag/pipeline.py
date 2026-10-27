"""One fenced FIFO parent for SYNC, internal Item replay and safe resume.

No authorization policy is inferred here. Callers must authorize project_manage.
Original revisions stay immutable; activation belongs only to IndexService.
"""
import json
import re
import sqlite3
import time
import uuid

from almrag.embedding import fingerprint
from almrag.processing import ProcessingError, _json
from almrag.queue import LeaseLost, Queue
from almrag.storage import canonical_uid


class PipelineError(ProcessingError):pass


RECENT_PREFLIGHT_SECONDS=900
STAGES=('COLLECT','PROCESS','EMBED','INDEX')
RECOVERABLE=frozenset(('MODEL_SERVER_PAUSED','VECTOR_SERVER_PAUSED','VECTOR_TRANSPORT_ERROR',
    'MODEL_TRANSPORT_ERROR','VECTOR_DEADLINE_EXCEEDED','HTTP_429','HTTP_503','ABORTED',
    'ABORT_REQUESTED','STORAGE_ERROR','SERVER_PAUSED','CIRCUIT_OPEN','RATE_LIMITED','VECTOR_BATCH_INVALID','MODEL_RESPONSE_SCHEMA_MISMATCH'))


def _code(error):
    code=getattr(error,'code','GLOBAL_ERROR')
    return code if isinstance(code,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',code) else 'GLOBAL_ERROR'


class PipelineService:
    def __init__(self,db,collection,processing,indexing,*,fault_hook=lambda event:None):
        self.db,self.collection,self.processing,self.indexing=db,collection,processing,indexing
        self.queue=Queue(db);self.fault_hook=fault_hook;self._recent={}

    @staticmethod
    def _signature(snapshot):return fingerprint({k:v for k,v in snapshot.items() if k!='refs'})

    @staticmethod
    def _guard(c,job):Queue._guard(c,job['job_id'],job['fencing_token'],time.time())

    def _live(self,job,abort_check):
        with self.db.transaction() as c:self._guard(c,job)
        if abort_check():raise PipelineError('ABORT_REQUESTED',stop_state='PAUSED')

    def _prepare(self,project_uid,reuse=False):
        # Enumerating every Tracker is throttled and slow, so the sync that follows a preflight
        # reuses its ALM catalog snapshot; local processing state is always recomputed.
        recent=self._recent.get(project_uid)
        if reuse and recent and time.monotonic()-recent[0]<RECENT_PREFLIGHT_SECONDS:pre,collection=recent[1],recent[2]
        else:
            pre,collection=self.collection._preflight(project_uid)
            self._recent[project_uid]=(time.monotonic(),pre,collection)
        _,processing=self.processing._prepare(project_uid)
        snapshot={'project_uid':project_uid,'collection':collection,'processing':processing}
        return {'status':'READY','sync_ready':True,'config_revision':fingerprint(snapshot),
                'estimated_items':pre['estimated_items'],'diagnostics':[]},snapshot

    def preflight(self,project_uid):
        try:return self._prepare(project_uid)[0]
        except (LeaseLost,sqlite3.Error):raise
        except Exception as error:return {'status':'BLOCKED','sync_ready':False,'config_revision':None,'estimated_items':None,'diagnostics':[_code(error)]}

    def enqueue(self,project_uid,stage='SYNC',config_revision=None):
        if stage!='SYNC':raise PipelineError('STAGE_NOT_IMPLEMENTED')
        pre,snapshot=self._prepare(project_uid,reuse=config_revision is not None)
        self._recent.pop(project_uid,None)
        if config_revision is not None and pre['config_revision']!=config_revision:raise PipelineError('STALE_PREFLIGHT')
        job_id=str(uuid.uuid4());now=time.time()
        with self.db.transaction() as c:
            self._config_current(c,snapshot)
            c.execute('INSERT INTO jobs(job_id,project_uid,stage,created_at,updated_at,progress_total) VALUES(?,?,?,?,?,?)',(job_id,project_uid,'SYNC',now,now,pre['estimated_items']))
            c.execute('INSERT INTO pipeline_runs VALUES(?,?,?)',(job_id,fingerprint(snapshot),_json(snapshot)))
            c.execute('INSERT INTO collection_snapshots VALUES(?,?,?)',(job_id,fingerprint(snapshot['collection']),_json(snapshot['collection'])))
            Queue._event(c,job_id,'QUEUED',now)
        return self.queue.get_job(job_id)

    def _config_current(self,c,snapshot):
        processing=snapshot['processing']
        if self.processing._config(snapshot['project_uid'],c)!=processing['config']:raise PipelineError('PROCESSING_CONFIG_CHANGED')
        if snapshot.get('collection'):
            current=self.collection._config(snapshot['project_uid'],c)
            if current!={k:snapshot['collection'][k] for k in current}:raise PipelineError('COLLECTION_CONFIG_CHANGED')

    def _snapshot(self,job):
        with self.db.connect() as c:row=c.execute('SELECT * FROM pipeline_runs WHERE job_id=?',(job['job_id'],)).fetchone()
        if row is None:raise PipelineError('PIPELINE_SNAPSHOT_MISSING')
        try:snapshot=json.loads(row['snapshot'])
        except (TypeError,ValueError):raise PipelineError('SNAPSHOT_INTEGRITY_ERROR') from None
        if fingerprint(snapshot)!=row['config_revision'] or snapshot['project_uid']!=job['project_uid']:raise PipelineError('SNAPSHOT_INTEGRITY_ERROR')
        return snapshot

    def _check_current(self,job,snapshot,abort_check):
        self._live(job,abort_check)
        _,current=self.processing._prepare(job['project_uid'])
        if self._signature(current)!=self._signature(snapshot['processing']):raise PipelineError('MODEL_RUNTIME_DRIFT')
        with self.db.connect() as c:self._config_current(c,snapshot)
        if snapshot.get('replay'):
            # Explicit recollection may legitimately create a newer revision.
            # Once checkpointed, validate that run's new pin rather than the
            # original failure's revision used to authorize recollection.
            if not self._checkpoint_refs(job):self._replay_ref(snapshot['replay'],job['project_uid'])

    def _checkpoint_refs(self,job):
        with self.db.connect() as c:
            row=c.execute('SELECT snapshot,config_revision FROM pipeline_processing_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()
            if row is None:return False
            value=json.loads(row['snapshot'])
            if fingerprint(value)!=row['config_revision']:raise PipelineError('SNAPSHOT_INTEGRITY_ERROR')
            for ref in value['refs']:self._ref_current(c,job,ref)
        return True

    def _replay_ref(self,replay,project_uid):
        with self.db.connect() as c:
            row=c.execute("SELECT i.item_uid,i.source_item_id,s.latest_revision_uid AS revision_uid,m.scope_id,m.state,i.deleted_state FROM collection_memberships m LEFT JOIN items i ON i.project_uid=m.project_uid AND i.source_item_id=m.source_item_id LEFT JOIN item_collection_state s USING(item_uid) WHERE m.project_uid=? AND m.source_item_id=?",(project_uid,replay['source_item_id'])).fetchone()
            allowed=bool(row and self._selected_scope(c,project_uid,row['scope_id']))
        if not allowed or row['state']!='IN_SCOPE' or (row['item_uid'] and row['deleted_state']!='active'):raise PipelineError('REPLAY_SCOPE_CHANGED')
        if replay.get('revision_uid') is not None and row['revision_uid']!=replay['revision_uid']:raise PipelineError('STALE_REVISION')
        if not row['item_uid'] and replay['from_stage']!='COLLECT':raise PipelineError('PINNED_REVISION_MISSING')
        return {key:row[key] for key in ('item_uid','source_item_id','revision_uid','scope_id')}

    @staticmethod
    def _selected_scope(c,project_uid,scope_id):
        selection=c.execute('SELECT selection_mode,scope_ids FROM project_selections WHERE project_uid=?',(project_uid,)).fetchone()
        if selection is None:return False
        return selection['selection_mode']=='ALL' or scope_id in json.loads(selection['scope_ids'])

    def _processing_snapshot(self,job,snapshot):
        with self.db.connect() as c:stored=c.execute('SELECT * FROM pipeline_processing_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()
        if stored:
            value=json.loads(stored['snapshot'])
            if fingerprint(value)!=stored['config_revision'] or self._signature(value)!=self._signature(snapshot['processing']):raise PipelineError('SNAPSHOT_INTEGRITY_ERROR')
            return value
        _,current=self.processing._prepare(job['project_uid'])
        if self._signature(current)!=self._signature(snapshot['processing']):raise PipelineError('MODEL_RUNTIME_DRIFT')
        if job['stage']=='SYNC' or snapshot.get('replay',{}).get('from_stage')=='COLLECT':
            with self.db.connect() as c:successful={r[0] for r in c.execute("SELECT source_item_id FROM collection_outcomes WHERE job_id=? AND state='SUCCEEDED'",(job['job_id'],))}
            current['refs']=[ref for ref in current['refs'] if ref['source_item_id'] in successful]
        else:current['refs']=[self._replay_ref(snapshot['replay'],job['project_uid'])]
        with self.db.transaction() as c:
            self._guard(c,job);self._config_current(c,snapshot)
            c.execute('INSERT INTO pipeline_processing_snapshots VALUES(?,?,?)',(job['job_id'],fingerprint(current),_json(current)))
        return current

    def _ref_current(self,c,job,ref):
        row=c.execute("SELECT i.item_uid,i.source_item_id,s.latest_revision_uid AS revision_uid,m.scope_id FROM items i JOIN item_collection_state s USING(item_uid) JOIN collection_memberships m ON m.project_uid=i.project_uid AND m.source_item_id=i.source_item_id WHERE i.project_uid=? AND i.item_uid=? AND m.state='IN_SCOPE' AND i.deleted_state='active'",(job['project_uid'],ref['item_uid'])).fetchone()
        actual=dict(row) if row else None
        if actual!=ref or not self._selected_scope(c,job['project_uid'],ref['scope_id']):raise PipelineError('PINNED_INPUT_CHANGED',False)

    def _record(self,job,ref,stage,result=None,error=None):
        with self.db.transaction() as c:
            self._guard(c,job)
            c.execute('INSERT INTO pipeline_steps VALUES(?,?,?,?,?,?,?)',(job['job_id'],ref['item_uid'],ref['revision_uid'],stage,'FAILED' if error else 'SUCCEEDED',result,error))
            if error:
                c.execute('INSERT OR IGNORE INTO failed_items(failed_item_uid,job_id,project_uid,item_uid,revision_uid,failed_stage,error_class,retryable) VALUES(?,?,?,?,?,?,?,1)',(canonical_uid(job['job_id'],ref['item_uid'],stage),job['job_id'],job['project_uid'],ref['item_uid'],ref['revision_uid'],stage,error))
            c.execute('UPDATE jobs SET checkpoint=?,updated_at=? WHERE job_id=?',(_json({'stage':stage,'last_item_uid':ref['item_uid']}),time.time(),job['job_id']))

    def _process_stages(self,job,snapshot,processing,abort_check):
        runtime=self.processing.runtime_factory(job['project_uid'])
        if runtime is None:raise PipelineError('MODEL_PROFILE_UNCONFIGURED')
        previous=runtime.abort_check
        def check():self._live(job,abort_check);return False
        runtime.abort_check=check
        try:
            _,profile=self.processing._runtime(job['project_uid'],runtime)
            if profile['fingerprint']!=processing['model_fingerprint']:raise PipelineError('MODEL_RUNTIME_DRIFT')
            start=snapshot.get('replay',{}).get('from_stage','COLLECT')
            for ref in processing['refs']:
                for stage,operation in [('PROCESS',self.processing._process),('EMBED',self.processing._embed)]:
                    if STAGES.index(stage)<STAGES.index(start):continue
                    self._live(job,abort_check)
                    with self.db.connect() as c:
                        done=c.execute('SELECT state FROM pipeline_steps WHERE job_id=? AND item_uid=? AND stage=?',(job['job_id'],ref['item_uid'],stage)).fetchone()
                        prior=c.execute("SELECT 1 FROM pipeline_steps WHERE job_id=? AND item_uid=? AND state='FAILED'",(job['job_id'],ref['item_uid'])).fetchone()
                    if prior:break
                    if done:continue
                    try:
                        with self.db.connect() as c:self._config_current(c,snapshot);self._ref_current(c,job,ref)
                        result=operation(dict(job,stage=stage),processing,ref,runtime,abort_check)
                        self._live(job,abort_check);self._record(job,ref,stage,result=result)
                        self.fault_hook('after_'+stage)
                    except (LeaseLost,sqlite3.Error,OSError):raise
                    except Exception as error:
                        if getattr(error,'global_error',True):raise
                        self._record(job,ref,stage,error=_code(error));break
        finally:runtime.abort_check=previous

    def _index(self,job,snapshot,processing,abort_check):
        with self.db.connect() as c:stored=c.execute('SELECT 1 FROM index_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()
        if stored:
            with self.db.connect() as c:index_snapshot=json.loads(c.execute('SELECT snapshot FROM index_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()[0])
        else:
            try:_,index_snapshot=self.indexing._prepare(job['project_uid'],'INDEX')
            except Exception as error:
                if _code(error)!='REBUILD_REQUIRED':raise
                _,index_snapshot=self.indexing._prepare(job['project_uid'],'REBUILD')
            with self.db.connect() as c:
                failed=bool(c.execute("SELECT 1 FROM pipeline_steps WHERE job_id=? AND state='FAILED'",(job['job_id'],)).fetchone() or c.execute("SELECT 1 FROM collection_outcomes WHERE job_id=? AND state='FAILED'",(job['job_id'],)).fetchone())
            expected={ref['item_uid']:ref for ref in processing['refs']}
            ready=[]
            for ref in index_snapshot['processing']['refs']:
                result=self.processing._result(ref['revision_uid'],self.processing._item_policy(processing,ref)[1])
                if ref['item_uid'] in expected and ref==expected[ref['item_uid']] and result and result['state']=='EMBED_READY':ready.append(ref)
            if index_snapshot['stage']=='REBUILD':
                # Never shrink expected new-generation coverage around failed Items.
                if failed or ready!=index_snapshot['processing']['refs']:raise PipelineError('REBUILD_INCOMPLETE')
            else:index_snapshot['processing']['refs']=ready
            index_snapshot['generation_uid']=index_snapshot['previous_generation_uid'] if index_snapshot['stage']=='INDEX' and index_snapshot['previous_generation_uid'] else str(uuid.uuid4())
            with self.db.transaction() as c:
                self._guard(c,job);self._config_current(c,snapshot)
                c.execute('INSERT INTO index_snapshots VALUES(?,?,?)',(job['job_id'],fingerprint(index_snapshot),_json(index_snapshot)))
        self._live(job,abort_check)
        result=self.indexing.run(dict(job,stage=index_snapshot['stage']),abort_check,finish=False)
        if result['state'] not in {'SUCCEEDED','COMPLETED_WITH_ERRORS'}:raise PipelineError(result['error_code'] or 'INDEX_FAILED',stop_state=result['state'])
        self.fault_hook('after_INDEX')

    def _complete(self,job):
        with self.db.transaction() as c:
            self._guard(c,job)
            failed_sources={r[0] for r in c.execute("SELECT source_item_id FROM collection_outcomes WHERE job_id=? AND state='FAILED'",(job['job_id'],))}
            failed_items={r[0] for r in c.execute("SELECT item_uid FROM pipeline_steps WHERE job_id=? AND state='FAILED' UNION SELECT item_uid FROM index_outcomes WHERE job_id=? AND state='FAILED'",(job['job_id'],job['job_id']))}
            failed_sources.update(r[0] for item in failed_items for r in c.execute('SELECT source_item_id FROM items WHERE item_uid=?',(item,)))
            succeeded=c.execute("SELECT count(*) FROM index_outcomes WHERE job_id=? AND state='SUCCEEDED'",(job['job_id'],)).fetchone()[0]
            skipped=c.execute("SELECT count(*) FROM collection_outcomes WHERE job_id=? AND state='SKIPPED'",(job['job_id'],)).fetchone()[0]
            failed=len(failed_sources)
            c.execute('UPDATE jobs SET progress_total=?,succeeded_items=?,failed_items=?,skipped_items=?,checkpoint=?,updated_at=? WHERE job_id=?',(succeeded+failed+skipped,succeeded,failed,skipped,_json({'stage':'DONE','outcomes':succeeded+failed+skipped}),time.time(),job['job_id']))
            replay=c.execute('SELECT * FROM pipeline_replays WHERE job_id=?',(job['job_id'],)).fetchone()
            if replay and not failed and succeeded:
                c.execute("UPDATE failed_items SET replay_state='RESOLVED' WHERE job_id=? AND item_uid=? AND failed_stage=? AND revision_uid=?",(replay['original_job_id'],replay['item_uid'],replay['failed_stage'],replay['revision_uid']))
                if replay['failed_stage']=='COLLECT':c.execute("UPDATE collection_failures SET replay_state='RESOLVED' WHERE job_id=? AND source_item_id=?",(replay['original_job_id'],replay['source_item_id']))
        return 'COMPLETED_WITH_ERRORS' if failed else 'SUCCEEDED'

    def run(self,job,abort_check=lambda:False):
        try:
            if job['stage'] not in {'SYNC','REPLAY'}:raise PipelineError('STAGE_NOT_IMPLEMENTED')
            snapshot=self._snapshot(job);self._check_current(job,snapshot,abort_check)
            if job['stage']=='SYNC' or snapshot.get('replay',{}).get('from_stage')=='COLLECT':
                with self.db.connect() as c:collected=c.execute('SELECT 1 FROM pipeline_processing_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()
                if not collected:
                    result=self.collection.run(dict(job,stage='COLLECT'),abort_check,finish=False)
                    if result['state'] not in {'SUCCEEDED','COMPLETED_WITH_ERRORS'}:raise PipelineError(result['error_code'] or 'COLLECTION_FAILED',stop_state=result['state'])
            processing=self._processing_snapshot(job,snapshot);self.fault_hook('after_COLLECT')
            self._process_stages(job,snapshot,processing,abort_check)
            self._index(job,snapshot,processing,abort_check)
            self._live(job,abort_check);state=self._complete(job)
            self.queue.finish(job['job_id'],job['fencing_token'],state)
            return state
        except LeaseLost:raise
        except Exception as error:
            state=getattr(error,'stop_state','BLOCKED')
            if state not in {'BLOCKED','PAUSED','FAILED','CANCELLED'}:state='BLOCKED'
            code='STORAGE_ERROR' if isinstance(error,(sqlite3.Error,OSError)) else _code(error)
            self.queue.finish(job['job_id'],job['fencing_token'],state,code)
            return state

    def list_failures(self,job_id,limit=100,offset=0):
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=1000 or isinstance(offset,bool) or not isinstance(offset,int) or offset<0:raise PipelineError('FAILURE_PAGE_INVALID')
        if self.queue.get_job(job_id) is None:raise PipelineError('JOB_NOT_FOUND')
        with self.db.connect() as c:
            rows=[dict(r) for r in c.execute("SELECT f.failed_item_uid,f.job_id,f.project_uid,f.item_uid,i.source_item_id,f.revision_uid,f.failed_stage,f.error_class AS error_code,f.retryable,f.replay_state FROM failed_items f JOIN items i USING(item_uid) WHERE f.job_id=? UNION ALL SELECT NULL,job_id,project_uid,item_uid,source_item_id,revision_uid,'COLLECT',error_code,retryable,replay_state FROM collection_failures WHERE job_id=? ORDER BY source_item_id,failed_stage LIMIT ? OFFSET ?",(job_id,job_id,limit,offset))]
        return rows

    def retry(self,job_id,item_uid,from_stage='FAILED_STAGE',force_recollect=False,expected_revision_uid=None):
        original=self.queue.get_job(job_id)
        if original is None:raise PipelineError('JOB_NOT_FOUND')
        if original['state'] in {'RUNNING','QUEUED'}:raise PipelineError('RETRY_STATE_INVALID')
        failures=[];offset=0
        while True:
            page=self.list_failures(job_id,1000,offset)
            failures.extend(f for f in page if f['item_uid']==item_uid or (f['item_uid'] is None and f['source_item_id']==item_uid))
            if len(page)<1000:break
            offset+=len(page)
        if not failures:raise PipelineError('FAILURE_NOT_FOUND')
        failure=min(failures,key=lambda f:STAGES.index(f['failed_stage']))
        if not failure['retryable']:raise PipelineError('FAILURE_NOT_RETRYABLE')
        if expected_revision_uid is not None and expected_revision_uid!=failure['revision_uid']:raise PipelineError('STALE_REVISION')
        start='COLLECT' if force_recollect else failure['failed_stage'] if from_stage=='FAILED_STAGE' else from_stage
        if start not in STAGES or STAGES.index(start)>STAGES.index(failure['failed_stage']):raise PipelineError('REPLAY_STAGE_INVALID')
        replay={'original_job_id':job_id,'source_item_id':failure['source_item_id'],'item_uid':failure['item_uid'],'revision_uid':failure['revision_uid'],'failed_stage':failure['failed_stage'],'from_stage':start}
        self._replay_ref(replay,original['project_uid'])
        _,processing=self.processing._prepare(original['project_uid'])
        snapshot={'project_uid':original['project_uid'],'processing':processing,'collection':None,'replay':replay}
        if start=='COLLECT':
            _,collection=self.collection._preflight(original['project_uid'])
            adapter=self.collection.connector_factory(collection['instance_uid'])
            refs=[r for r in adapter.iter_refs(collection['source_project_id'],collection['source_scope_ids']) if str(r['id'])==failure['source_item_id']]
            if len(refs)!=1:raise PipelineError('REPLAY_SCOPE_CHANGED')
            collection.update(refs=refs,targeted_replay=True);snapshot['collection']=collection
        signature=self._signature(processing)
        key=fingerprint([job_id,failure['source_item_id'],start,failure['revision_uid'],signature])
        now=time.time();new_job=str(uuid.uuid4())
        with self.db.transaction() as c:
            self._config_current(c,snapshot)
            existing=c.execute('SELECT job_id FROM pipeline_replays WHERE replay_key=?',(key,)).fetchone()
            if existing:return Queue._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(existing[0],)).fetchone())
            c.execute('INSERT INTO jobs(job_id,project_uid,stage,created_at,updated_at,progress_total) VALUES(?,?,?,?,?,1)',(new_job,original['project_uid'],'REPLAY',now,now))
            c.execute('INSERT INTO pipeline_runs VALUES(?,?,?)',(new_job,fingerprint(snapshot),_json(snapshot)))
            c.execute('INSERT INTO pipeline_replays VALUES(?,?,?,?,?,?,?,?,?)',(key,new_job,job_id,failure['source_item_id'],failure['item_uid'],failure['revision_uid'],failure['failed_stage'],start,signature))
            if snapshot['collection']:c.execute('INSERT INTO collection_snapshots VALUES(?,?,?)',(new_job,fingerprint(snapshot['collection']),_json(snapshot['collection'])))
            Queue._event(c,new_job,'QUEUED',now)
        return self.queue.get_job(new_job)

    def retry_all(self,job_id,from_stage='FAILED_STAGE',force_recollect=False,expected_revision_uid=None):
        result=[];seen=set();offset=0
        while True:
            page=self.list_failures(job_id,1000,offset)
            for failure in page:
                key=failure['item_uid'] or failure['source_item_id']
                if key not in seen and failure['replay_state']!='RESOLVED':
                    result.append(self.retry(job_id,key,from_stage,force_recollect,expected_revision_uid));seen.add(key)
            if len(page)<1000:return result
            offset+=len(page)

    def pause(self,job_id):
        job=self.queue.request_pause(job_id)
        if job is None:raise PipelineError('JOB_NOT_FOUND')
        if job.pop('rejected',False):raise PipelineError('PAUSE_STATE_INVALID')
        return job

    def resume(self,job_id):
        job=self.queue.get_job(job_id)
        if job is None:raise PipelineError('JOB_NOT_FOUND')
        if job['state'] not in {'PAUSED','BLOCKED'}:raise PipelineError('RESUME_STATE_INVALID')
        if job['last_error_code'] not in RECOVERABLE:raise PipelineError('RESUME_NOT_RECOVERABLE')
        if job['stage'] in {'SYNC','REPLAY'}:
            snapshot=self._snapshot(job)
            _,current=self.processing._prepare(job['project_uid'])
            if self._signature(current)!=self._signature(snapshot['processing']):raise PipelineError('MODEL_RUNTIME_DRIFT')
            with self.db.connect() as c:self._config_current(c,snapshot)
            checkpointed=self._checkpoint_refs(job)
            if snapshot.get('replay') and not checkpointed:self._replay_ref(snapshot['replay'],job['project_uid'])
        elif job['stage'] in {'PROCESS','EMBED'}:
            snapshot=self.processing._snapshot(job);_,current=self.processing._prepare(job['project_uid'])
            if self._signature(current)!=self._signature(snapshot):raise PipelineError('MODEL_RUNTIME_DRIFT')
            with self.db.connect() as c:
                for ref in snapshot['refs']:self._ref_current(c,job,ref)
        elif job['stage'] in {'INDEX','REBUILD'}:
            snapshot=self.indexing._snapshot(job);_,current=self.processing._prepare(job['project_uid'])
            if self.indexing._fingerprint(current)!=snapshot['config_fingerprint']:raise PipelineError('MODEL_RUNTIME_DRIFT')
            with self.db.connect() as c:
                self.indexing._config_current(c,snapshot)
                for ref in snapshot['processing']['refs']:self.indexing._ref_current(c,snapshot,ref)
        elif job['stage']=='COLLECT':
            snapshot=self.collection._snapshot(job)
            if self.collection._config(job['project_uid'])!={k:snapshot[k] for k in self.collection._config(job['project_uid'])}:raise PipelineError('COLLECTION_CONFIG_CHANGED')
        else:raise PipelineError('STAGE_NOT_IMPLEMENTED')
        with self.db.transaction() as c:
            current=c.execute('SELECT state,last_error_code FROM jobs WHERE job_id=?',(job_id,)).fetchone()
            if current['state']!=job['state'] or current['last_error_code']!=job['last_error_code']:raise PipelineError('RESUME_STATE_INVALID')
            c.execute("UPDATE jobs SET state='QUEUED',owner=NULL,fencing_token=NULL,lease_expires_at=NULL,updated_at=? WHERE job_id=?",(time.time(),job_id))
            Queue._event(c,job_id,'QUEUED',time.time(),'OPERATOR_RESUME')
        return self.queue.get_job(job_id)
