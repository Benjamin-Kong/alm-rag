"""Fenced dense/keyword publication and isolated all-or-nothing rebuilds."""
import hashlib
import json
import math
import sqlite3
import struct
import time
import uuid

from almrag.embedding import fingerprint
from almrag.lexical import LEXICAL_VERSION, LexicalIndex
from almrag.processing import ProcessingError, _json
from almrag.queue import LeaseLost, Queue
from almrag.readers import ReaderRegistry
from almrag.storage import canonical_uid
from almrag.source_scope import allows_scope


class IndexError(ProcessingError):
    pass


VECTOR_BATCH_SIZE=256
# The model runtime probe issues several Ollama calls, so it runs at most this often per claimed job instead of per item.
MODEL_RECHECK_SECONDS=300
MODEL_PROBE_ATTEMPTS=3
MODEL_PROBE_BACKOFF_SECONDS=(2,5)


def collection_name_for(generation_uid):
    return 'almrag_' + uuid.UUID(generation_uid).hex


def normalized_vector(vector, dimension):
    if not isinstance(vector,list) or len(vector)!=dimension or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in vector):
        raise IndexError('VECTOR_CACHE_CORRUPT')
    scale=max(abs(v) for v in vector)
    if not scale:raise IndexError('VECTOR_CACHE_CORRUPT')
    scaled=[v/scale for v in vector]
    norm=math.sqrt(sum(v*v for v in scaled))
    return [struct.unpack('!f',struct.pack('!f',v/norm))[0] for v in scaled]


class IndexService:
    def __init__(self,db,processing,vector_store,*,lexical=None,readers=None,fault_hook=lambda event:None):
        self.db,self.processing,self.vector_store=db,processing,vector_store
        self.lexical=lexical or LexicalIndex(db)
        self.readers=readers or ReaderRegistry(db)
        self.fault_hook=fault_hook
        self.queue=Queue(db)
        self._model_checked={}
        self.sleep=time.sleep

    @staticmethod
    def _guard(c,job):Queue._guard(c,job['job_id'],job['fencing_token'],time.time())

    def _live(self,job,abort_check):
        with self.db.transaction() as c:self._guard(c,job)
        if abort_check():raise IndexError('ABORT_REQUESTED',stop_state='PAUSED')

    @staticmethod
    def _fingerprint(snapshot):
        return fingerprint({'effective_policy':snapshot['config']['effective_policy'],'chunking':snapshot['chunking'],'model_fingerprint':snapshot['model_fingerprint'],'processor_versions':snapshot['processor_versions'],'lexical_version':LEXICAL_VERSION})

    def _prepare(self,project_uid,stage='INDEX'):
        if stage not in {'INDEX','REBUILD'}:raise IndexError('STAGE_NOT_IMPLEMENTED')
        _,processing=self.processing._prepare(project_uid)
        with self.db.connect() as c:
            active=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(project_uid,)).fetchone()[0]
            previous=c.execute('SELECT * FROM generation_configs WHERE generation_uid=?',(active,)).fetchone() if active else None
            if stage=='REBUILD':
                # Unknown missing is not confirmed deletion. Retain active revisions
                # in expected coverage or refuse to publish a partial replacement.
                missing=c.execute("SELECT i.item_uid,i.source_item_id,i.active_revision_uid AS revision_uid,m.scope_id FROM items i JOIN collection_memberships m ON m.project_uid=i.project_uid AND m.source_item_id=i.source_item_id WHERE i.project_uid=? AND i.active_revision_uid IS NOT NULL AND i.deleted_state='active' AND m.state='MISSING' ORDER BY i.item_uid",(project_uid,)).fetchall()
                processing['refs']=sorted(processing['refs']+[dict(r) for r in missing],key=lambda r:r['item_uid'])
            if c.execute('SELECT 1 FROM project_selections WHERE project_uid=?',(project_uid,)).fetchone() is None:raise IndexError('PROJECT_NOT_CONFIGURED')
            processing['refs']=[ref for ref in processing['refs'] if allows_scope(c,project_uid,ref['scope_id'])]
        config=self._fingerprint(processing)
        if active and (previous is None or previous['config_fingerprint']!=config) and stage=='INDEX':raise IndexError('REBUILD_REQUIRED')
        snapshot={'project_uid':project_uid,'stage':stage,'processing':processing,'config_fingerprint':config,'previous_generation_uid':active}
        revision=fingerprint(snapshot)
        ready=[]
        for ref in processing['refs']:
            result=self.processing._result(ref['revision_uid'],self.processing._item_policy(processing,ref)[1])
            ready.append(bool(result and result['state']=='EMBED_READY'))
        pre={'status':'READY','index_ready':all(ready),'rebuild_ready':all(ready),'config_revision':revision,'estimated_items':len(ready),'diagnostics':[] if all(ready) else ['EMBED_REQUIRED']}
        return pre,snapshot

    def preflight(self,project_uid,stage='INDEX'):
        try:return self._prepare(project_uid,stage)[0]
        except (LeaseLost,sqlite3.Error):raise
        except Exception as error:return {'status':'BLOCKED','index_ready':False,'rebuild_ready':False,'config_revision':None,'estimated_items':None,'diagnostics':[getattr(error,'code','INDEX_PREFLIGHT_FAILED')]}

    def enqueue(self,project_uid,stage='INDEX',config_revision=None):
        pre,snapshot=self._prepare(project_uid,stage)
        if config_revision is not None and config_revision!=pre['config_revision']:raise IndexError('STALE_PREFLIGHT')
        snapshot['generation_uid']=snapshot['previous_generation_uid'] if stage=='INDEX' and snapshot['previous_generation_uid'] else str(uuid.uuid4())
        job_id=str(uuid.uuid4());now=time.time()
        with self.db.transaction() as c:
            if self.processing._config(project_uid,c)!=snapshot['processing']['config']:raise IndexError('STALE_PREFLIGHT')
            current=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(project_uid,)).fetchone()[0]
            if current!=snapshot['previous_generation_uid']:raise IndexError('STALE_PREFLIGHT')
            c.execute('INSERT INTO jobs(job_id,project_uid,stage,created_at,updated_at,progress_total) VALUES(?,?,?,?,?,?)',(job_id,project_uid,stage,now,now,len(snapshot['processing']['refs'])))
            c.execute('INSERT INTO index_snapshots VALUES(?,?,?)',(job_id,fingerprint(snapshot),_json(snapshot)))
            Queue._event(c,job_id,'QUEUED',now)
            return Queue._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone())

    def _snapshot(self,job):
        with self.db.connect() as c:row=c.execute('SELECT * FROM index_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()
        if row is None:raise IndexError('INDEX_SNAPSHOT_MISSING')
        snapshot=json.loads(row['snapshot'])
        if fingerprint(snapshot)!=row['config_revision'] or snapshot['project_uid']!=job['project_uid'] or snapshot['stage']!=job['stage']:raise IndexError('SNAPSHOT_INTEGRITY_ERROR')
        if snapshot['config_fingerprint']!=self._fingerprint(snapshot['processing']):raise IndexError('REBUILD_REQUIRED')
        return snapshot

    def _config_current(self,c,snapshot):
        processing=snapshot['processing']
        if self.processing._config(snapshot['project_uid'],c)!=processing['config']:raise IndexError('PROCESSING_CONFIG_CHANGED')
        active=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(snapshot['project_uid'],)).fetchone()[0]
        if active not in {snapshot['previous_generation_uid'],snapshot['generation_uid']}:raise IndexError('GENERATION_CHANGED')

    def _ref_current(self,c,snapshot,ref):
        actual=c.execute("SELECT i.active_revision_uid,i.deleted_state,s.latest_revision_uid,m.scope_id,m.state FROM items i JOIN item_collection_state s USING(item_uid) JOIN collection_memberships m ON m.project_uid=i.project_uid AND m.source_item_id=i.source_item_id WHERE i.item_uid=? AND i.project_uid=?",(ref['item_uid'],snapshot['project_uid'])).fetchone()
        valid=actual and actual['deleted_state']=='active' and actual['scope_id']==ref['scope_id'] and ((actual['state']=='IN_SCOPE' and actual['latest_revision_uid']==ref['revision_uid']) or (snapshot['stage']=='REBUILD' and actual['state']=='MISSING' and actual['active_revision_uid']==ref['revision_uid']))
        if not valid or not allows_scope(c,snapshot['project_uid'],ref['scope_id']):raise IndexError('PINNED_INPUT_CHANGED',False)

    def _initialize(self,job,snapshot):
        generation=snapshot['generation_uid'];processing=snapshot['processing']
        with self.db.transaction() as c:
            self._guard(c,job);self._config_current(c,snapshot)
            c.execute('INSERT INTO index_generations(generation_uid,project_uid,model_config) VALUES(?,?,?) ON CONFLICT(generation_uid) DO NOTHING',(generation,job['project_uid'],_json(processing['runtime_profile'])))
            c.execute('INSERT INTO generation_configs(generation_uid,config_fingerprint,model_profile,processing_config,lexical_version,collection_name,expected_refs) VALUES(?,?,?,?,?,?,?) ON CONFLICT(generation_uid) DO NOTHING',(generation,snapshot['config_fingerprint'],_json(processing['runtime_profile']),_json(processing),LEXICAL_VERSION,collection_name_for(generation),_json(processing['refs'])))
            existing=c.execute('SELECT config_fingerprint,cleanup_state FROM generation_configs WHERE generation_uid=?',(generation,)).fetchone()
            if existing['config_fingerprint']!=snapshot['config_fingerprint']:raise IndexError('GENERATION_CONFIG_MISMATCH')
            if existing['cleanup_state']=='PENDING':
                c.execute("UPDATE generation_configs SET cleanup_state='ACTIVE' WHERE generation_uid=?",(generation,))
                c.execute("UPDATE index_generations SET state='PREPARED',validation_evidence=NULL,activated_at=NULL WHERE generation_uid=?",(generation,))
            elif existing['cleanup_state']!='ACTIVE':raise IndexError('GENERATION_CLEANED')

    def _points(self,snapshot,ref):
        processing=snapshot['processing'];model=processing['model_fingerprint'];dimension=processing['runtime_profile']['config']['vector_dimension']
        result=self.processing._result(ref['revision_uid'],self.processing._item_policy(processing,ref)[1])
        if result is None or result['state']!='EMBED_READY':raise IndexError('EMBED_REQUIRED',False)
        with self.db.connect() as c:
            chunks=[dict(r) for r in c.execute('SELECT c.* FROM chunks c JOIN processing_membership m USING(chunk_uid) WHERE m.result_uid=? ORDER BY chunk_uid',(result['result_uid'],))]
            manifest=c.execute('SELECT * FROM embedding_manifests WHERE result_uid=?',(result['result_uid'],)).fetchone()
            vectors={r['chunk_uid']:dict(r) for r in c.execute('SELECT v.chunk_uid,v.project_uid,v.content_hash,v.model_fingerprint,e.vector_json,e.vector_digest,e.dimension FROM embedding_chunk_vectors v JOIN embedding_cache e USING(project_uid,content_hash,model_fingerprint) WHERE v.result_uid=?',(result['result_uid'],))}
        digest=fingerprint([(x['chunk_uid'],x['content_hash']) for x in chunks])
        if not manifest or manifest['chunk_count']!=len(chunks) or manifest['manifest_digest']!=digest or manifest['model_fingerprint']!=model or set(vectors)!={x['chunk_uid'] for x in chunks}:raise IndexError('EMBEDDING_COVERAGE_MISMATCH')
        points=[]
        for chunk in chunks:
            cached=vectors[chunk['chunk_uid']]
            try:vector=json.loads(cached['vector_json'])
            except (ValueError,TypeError):raise IndexError('VECTOR_CACHE_CORRUPT') from None
            if hashlib.sha256(chunk['input_text'].encode()).hexdigest()!=chunk['embedding_input_digest'] or chunk['revision_uid']!=ref['revision_uid']:raise IndexError('CHUNK_INTEGRITY_ERROR')
            if cached['dimension']!=dimension or fingerprint(vector)!=cached['vector_digest'] or cached['content_hash']!=chunk['content_hash'] or cached['project_uid']!=snapshot['project_uid'] or cached['model_fingerprint']!=model or chunk['model_fingerprint']!=model:raise IndexError('VECTOR_CACHE_CORRUPT')
            vector=normalized_vector(vector,dimension)
            payload={'project_uid':snapshot['project_uid'],'generation_uid':snapshot['generation_uid'],'item_uid':ref['item_uid'],'revision_uid':ref['revision_uid'],'chunk_uid':chunk['chunk_uid'],'result_uid':result['result_uid'],'content_hash':chunk['content_hash'],'model_fingerprint':model,'vector_digest':fingerprint(vector)}
            points.append({'id':canonical_uid('point',snapshot['generation_uid'],chunk['chunk_uid']),'vector':vector,'payload':payload,'input_text':chunk['input_text']})
        return result['result_uid'],points

    @staticmethod
    def _dense(points):return [{k:p[k] for k in ('id','payload','vector')} for p in points]

    def _stage(self,job,snapshot,ref,abort_check):
        self._live(job,abort_check)
        result,points=self._points(snapshot,ref)
        collection=collection_name_for(snapshot['generation_uid'])
        dense=self._dense(points)
        for start in range(0,len(dense),VECTOR_BATCH_SIZE):
            self._live(job,abort_check)
            self.vector_store.upsert(collection,dense[start:start+VECTOR_BATCH_SIZE])
        self._live(job,abort_check);self.fault_hook('after_dense')
        self._verify_dense(collection,points)
        self._live(job,abort_check)
        with self.db.transaction() as c:
            self._guard(c,job)
            for point in points:
                self.lexical.put(c,point)
                c.execute("INSERT INTO index_points VALUES(?,?,?,'PREPARED',?) ON CONFLICT(point_uuid) DO NOTHING",(point['id'],snapshot['generation_uid'],point['payload']['chunk_uid'],point['payload']['content_hash']))
            documents=self._lexical_rows(c,snapshot['generation_uid'],result)
            if {r['point_uuid'] for r in documents}!={p['id'] for p in points}:raise IndexError('LEXICAL_COVERAGE_MISMATCH')
            self._check_fts(c,documents)
        self._live(job,abort_check);self.fault_hook('after_lexical')
        return {'ref':ref,'result_uid':result,'points':points,'lexical_digest':fingerprint(documents)}

    def _verify_dense(self,collection,points):
        # Items can have more chunks than the store accepts per call; the item is still published atomically afterwards.
        found=[]
        for start in range(0,len(points),VECTOR_BATCH_SIZE):
            found.extend(self.vector_store.retrieve(collection,[p['id'] for p in points[start:start+VECTOR_BATCH_SIZE]]))
        if len(found)!=len(points) or {p.get('id') for p in found}!={p['id'] for p in points}:raise IndexError('DENSE_COVERAGE_MISMATCH')
        expected={p['id']:p for p in points}
        for row in found:
            wanted=expected[row['id']];vector=row.get('vector')
            if row.get('payload')!=wanted['payload'] or not isinstance(vector,list) or len(vector)!=len(wanted['vector']) or any(isinstance(a,bool) or not isinstance(a,(float,int)) or not math.isfinite(a) or abs(a-b)>1e-5 for a,b in zip(vector,wanted['vector'])):raise IndexError('DENSE_COVERAGE_MISMATCH')

    def _check_model(self,job,snapshot,abort_check):
        key=(job['job_id'],job.get('fencing_token'));last=self._model_checked.get(key)
        if last is not None and time.monotonic()-last<MODEL_RECHECK_SECONDS:return
        for attempt in range(MODEL_PROBE_ATTEMPTS):
            try:
                _,profile=self.processing._runtime(job['project_uid']);break
            except Exception as error:
                if getattr(error,'code',None)!='MODEL_TRANSPORT_ERROR' or attempt==MODEL_PROBE_ATTEMPTS-1:raise
                self._live(job,abort_check);self.sleep(MODEL_PROBE_BACKOFF_SECONDS[min(attempt,len(MODEL_PROBE_BACKOFF_SECONDS)-1)])
        self._live(job,abort_check)
        if profile['fingerprint']!=snapshot['processing']['model_fingerprint']:raise IndexError('MODEL_RUNTIME_DRIFT')
        self._model_checked={k:v for k,v in self._model_checked.items() if k[0]==job['job_id']};self._model_checked[key]=time.monotonic()

    def _revalidate_external(self,job,snapshot,artifact,abort_check):
        self._live(job,abort_check)
        self._check_model(job,snapshot,abort_check)
        self._verify_dense(collection_name_for(snapshot['generation_uid']),artifact['points'])
        self._live(job,abort_check)

    @staticmethod
    def _check_fts(c,documents):
        found=LexicalIndex.fts_rows(c,[d['point_uuid'] for d in documents])
        for doc in documents:
            rows=found[doc['point_uuid']]
            if len(rows)!=1 or tuple(rows[0])!=(doc['terms'],doc['project_uid'],doc['generation_uid']):raise IndexError('LEXICAL_COVERAGE_MISMATCH')

    @staticmethod
    def _lexical_rows(c,generation,result):
        return [dict(r) for r in c.execute('SELECT d.* FROM keyword_documents d JOIN processing_membership m USING(chunk_uid) WHERE d.generation_uid=? AND m.result_uid=? ORDER BY d.point_uuid',(generation,result))]

    def _publish(self,c,job,snapshot,artifact):
        self._guard(c,job);self._config_current(c,snapshot)
        ref=artifact['ref'];self._ref_current(c,snapshot,ref)
        result=self.processing._item_policy(snapshot['processing'],ref)[1]
        row=c.execute('SELECT result_uid,state FROM processing_results WHERE revision_uid=? AND policy_fingerprint=?',(ref['revision_uid'],result)).fetchone()
        if row is None or row['state']!='EMBED_READY' or row['result_uid']!=artifact['result_uid']:raise IndexError('PROCESSING_RESULT_CHANGED')
        documents=self._lexical_rows(c,snapshot['generation_uid'],artifact['result_uid'])
        if fingerprint(documents)!=artifact['lexical_digest'] or {r['point_uuid'] for r in documents}!={p['id'] for p in artifact['points']}:raise IndexError('LEXICAL_COVERAGE_MISMATCH')
        self._check_fts(c,documents)
        current_result,current_points=self._points(snapshot,ref)
        if current_result!=artifact['result_uid'] or current_points!=artifact['points']:raise IndexError('EMBEDDING_COVERAGE_MISMATCH')
        dense=self._dense(artifact['points'])
        c.execute('INSERT INTO index_publications VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(generation_uid,item_uid) DO UPDATE SET result_uid=excluded.result_uid,revision_uid=excluded.revision_uid,points_digest=excluded.points_digest,point_count=excluded.point_count,dense_evidence=excluded.dense_evidence,lexical_digest=excluded.lexical_digest',(snapshot['generation_uid'],ref['item_uid'],artifact['result_uid'],ref['revision_uid'],fingerprint(dense),len(dense),_json(dense),artifact['lexical_digest']))
        c.executemany("UPDATE index_points SET vector_status='READY' WHERE point_uuid=?",[(p['id'],) for p in artifact['points']])
        c.execute('UPDATE items SET active_revision_uid=? WHERE item_uid=?',(ref['revision_uid'],ref['item_uid']))
        self._outcome(c,job,ref,artifact['result_uid'])

    @staticmethod
    def _outcome(c,job,ref,result_uid=None,error=None):
        c.execute('INSERT INTO index_outcomes VALUES(?,?,?,?,?,?) ON CONFLICT(job_id,item_uid) DO NOTHING',(job['job_id'],ref['item_uid'],ref['revision_uid'],result_uid,'FAILED' if error else 'SUCCEEDED',error))
        if error:c.execute('INSERT OR IGNORE INTO failed_items(failed_item_uid,job_id,project_uid,item_uid,revision_uid,failed_stage,error_class,retryable) VALUES(?,?,?,?,?,?,?,1)',(canonical_uid(job['job_id'],ref['item_uid'],'INDEX'),job['job_id'],job['project_uid'],ref['item_uid'],ref['revision_uid'],'INDEX',error))
        counts=dict(c.execute('SELECT state,count(*) FROM index_outcomes WHERE job_id=? GROUP BY state',(job['job_id'],)).fetchall())
        c.execute('UPDATE jobs SET succeeded_items=?,failed_items=?,checkpoint=?,updated_at=? WHERE job_id=?',(counts.get('SUCCEEDED',0),counts.get('FAILED',0),_json({'stage':'INDEX','last_item_uid':ref['item_uid'],'outcomes':sum(counts.values())}),time.time(),job['job_id']))

    def _activate(self,c,snapshot):
        generation=snapshot['generation_uid'];old=snapshot['previous_generation_uid']
        c.execute("UPDATE index_generations SET state='VALIDATED',validation_evidence=?,activated_at=? WHERE generation_uid=?",(_json({'verified':'exact dense+lexical manifests','expected_items':len(snapshot['processing']['refs'])}),str(time.time()),generation))
        c.execute('UPDATE projects SET active_generation_uid=? WHERE project_uid=?',(generation,snapshot['project_uid']))
        if old and old!=generation:
            c.execute("UPDATE index_generations SET state='RETIRED' WHERE generation_uid=?",(old,))
            c.execute("UPDATE generation_configs SET cleanup_state='PENDING' WHERE generation_uid=?",(old,))

    def run(self,job,abort_check=lambda:False,*,finish=True):
        previous=getattr(self.vector_store,'abort_check',None)
        try:
            self._live(job,abort_check);snapshot=self._snapshot(job)
            _,current=self.processing._prepare(job['project_uid'])
            if self._fingerprint(current)!=snapshot['config_fingerprint']:raise IndexError('MODEL_RUNTIME_DRIFT')
            self._initialize(job,snapshot)
            def check():self._live(job,abort_check);return False
            self.vector_store.abort_check=check
            self._live(job,abort_check)
            self.vector_store.ensure_collection(collection_name_for(snapshot['generation_uid']),snapshot['processing']['runtime_profile']['config']['vector_dimension'])
            self._live(job,abort_check)
            artifacts=[]
            for ref in snapshot['processing']['refs']:
                self._live(job,abort_check)
                with self.db.connect() as c:done=c.execute('SELECT state FROM index_outcomes WHERE job_id=? AND item_uid=?',(job['job_id'],ref['item_uid'])).fetchone()
                if done and job['stage']!='REBUILD':continue
                try:
                    artifact=self._stage(job,snapshot,ref,abort_check)
                    self.fault_hook('before_publish');self._live(job,abort_check)
                    self._revalidate_external(job,snapshot,artifact,abort_check)
                    if job['stage']=='REBUILD':artifacts.append(artifact)
                    else:
                        with self.db.transaction() as c:
                            self._publish(c,job,snapshot,artifact);self._activate(c,snapshot)
                        self.fault_hook('after_publish')
                except (LeaseLost,sqlite3.Error,OSError):raise
                except Exception as error:
                    if getattr(error,'global_error',True):raise
                    with self.db.transaction() as c:self._guard(c,job);self._outcome(c,job,ref,error=getattr(error,'code','ITEM_INDEX_FAILED'))
            with self.db.connect() as c:failed=c.execute("SELECT count(*) FROM index_outcomes WHERE job_id=? AND state='FAILED'",(job['job_id'],)).fetchone()[0]
            if job['stage']=='REBUILD':
                if failed or len(artifacts)!=len(snapshot['processing']['refs']):raise IndexError('REBUILD_INCOMPLETE')
                self._live(job,abort_check)
                for artifact in artifacts:self._revalidate_external(job,snapshot,artifact,abort_check)
                with self.db.transaction() as c:
                    self._guard(c,job);self._config_current(c,snapshot)
                    expected=[r for r in snapshot['processing']['refs'] if r not in current['refs']]
                    if [r for r in self.processing._refs(c,job['project_uid']) if allows_scope(c,job['project_uid'],r['scope_id'])]!=[r for r in snapshot['processing']['refs'] if r not in expected]:raise IndexError('REBUILD_INPUT_CHANGED')
                    for artifact in artifacts:self._publish(c,job,snapshot,artifact)
                    self._activate(c,snapshot)
                self.fault_hook('after_publish')
            elif not snapshot['processing']['refs']:
                with self.db.transaction() as c:self._guard(c,job);self._config_current(c,snapshot);self._activate(c,snapshot)
            state='COMPLETED_WITH_ERRORS' if failed else 'SUCCEEDED'
            if finish:self.queue.finish(job['job_id'],job['fencing_token'],state)
            return state if finish else {'state':state,'error_code':None}
        except LeaseLost:raise
        except Exception as error:
            state=getattr(error,'stop_state','BLOCKED')
            if state not in {'BLOCKED','PAUSED','FAILED','CANCELLED'}:state='BLOCKED'
            code='STORAGE_ERROR' if isinstance(error,(sqlite3.Error,OSError)) else getattr(error,'code','INDEX_FAILED')
            if 'snapshot' in locals():
                with self.db.transaction() as c:
                    self._guard(c,job)
                    generation=snapshot['generation_uid']
                    if not c.execute('SELECT 1 FROM projects WHERE active_generation_uid=?',(generation,)).fetchone():
                        c.execute("UPDATE index_generations SET state='FAILED' WHERE generation_uid=?",(generation,))
                        c.execute("UPDATE generation_configs SET cleanup_state='PENDING' WHERE generation_uid=? AND cleanup_state IN ('ACTIVE','PENDING')",(generation,))
            if finish:self.queue.finish(job['job_id'],job['fencing_token'],state,code)
            return state if finish else {'state':state,'error_code':code}
        finally:
            if previous is not None:self.vector_store.abort_check=previous

    def cleanup(self,job=None):
        removed=[]
        with self.db.connect() as c:pending=[dict(r) for r in c.execute("SELECT * FROM generation_configs WHERE cleanup_state IN ('PENDING','DELETING')")]
        for row in pending:
            with self.db.transaction() as c:
                if job:self._guard(c,job)
                current=c.execute('SELECT cleanup_state FROM generation_configs WHERE generation_uid=?',(row['generation_uid'],)).fetchone()
                if current is None or current[0] not in {'PENDING','DELETING'}:continue
                if c.execute('SELECT 1 FROM projects WHERE active_generation_uid=?',(row['generation_uid'],)).fetchone() or self.readers.has_readers(c,row['generation_uid']):continue
                c.execute("UPDATE generation_configs SET cleanup_state='DELETING' WHERE generation_uid=?",(row['generation_uid'],))
            if job:self._live(job,lambda:False)
            previous=getattr(self.vector_store,'abort_check',None)
            if job:
                def check():self._live(job,lambda:False);return False
                self.vector_store.abort_check=check
            try:self.vector_store.delete_collection(row['collection_name'])
            finally:
                if job and previous is not None:self.vector_store.abort_check=previous
            if job:self._live(job,lambda:False)
            with self.db.transaction() as c:
                if job:self._guard(c,job)
                if self.readers.has_readers(c,row['generation_uid']):raise IndexError('READER_APPEARED_DURING_CLEANUP')
                self.lexical.delete_generation(c,row['generation_uid'])
                c.execute("UPDATE index_points SET vector_status='RETIRED' WHERE generation_uid=?",(row['generation_uid'],))
                c.execute("UPDATE generation_configs SET cleanup_state='DELETED' WHERE generation_uid=?",(row['generation_uid'],))
            removed.append(row['generation_uid'])
        return removed
