"""Pinned, fenced M3 processing and selective vector persistence; no activation."""
import hashlib
import json
import math
import sqlite3
import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from almrag.chunking import CHUNKER_VERSION, TABLE_SERIALIZATION_VERSION, ChunkConfig, make_chunks
from almrag.embedding import ModelError, fingerprint
from almrag.normalization import VERSION as NORMALIZER_VERSION, normalize_field
from almrag.queue import LeaseLost, Queue
from almrag.storage import canonical_uid


def _json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


class ProcessingError(ValueError):
    def __init__(self,code,global_error=True,stop_state='BLOCKED'):
        super().__init__(code)
        self.code,self.global_error,self.stop_state=code,global_error,stop_state


class FieldRef(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    kind: Literal['NORMALIZED','SOURCE']
    key: str = Field(min_length=1,max_length=512)

    @model_validator(mode='after')
    def normalized_key(self):
        if self.kind=='NORMALIZED' and self.key not in {'title','description'}:
            raise ValueError('unsupported normalized field')
        return self


class ProcessingPolicy(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    fields: list[FieldRef] | None = None
    scope_fields: dict[str,list[FieldRef]] = Field(default_factory=dict)
    chunking: ChunkConfig | None = None

    @model_validator(mode='after')
    def unique_fields(self):
        for refs in [self.fields,*self.scope_fields.values()]:
            if refs is not None and len({(ref.kind,ref.key) for ref in refs})!=len(refs):
                raise ValueError('duplicate field reference')
        if any(not scope for scope in self.scope_fields):
            raise ValueError('empty scope identity')
        return self


class ProcessingService:
    def __init__(self,db,runtime_factory,*,allow_fixture=False):
        self.db,self.runtime_factory,self.allow_fixture=db,runtime_factory,allow_fixture
        self.queue=Queue(db)

    def configure(self,project_uid,policy):
        policy=ProcessingPolicy.model_validate(policy)
        with self.db.transaction() as c:
            if not c.execute('SELECT 1 FROM projects WHERE project_uid=?',(project_uid,)).fetchone():
                raise ProcessingError('PROJECT_NOT_CONFIGURED')
            c.execute('INSERT INTO processing_project_policies VALUES(?,?) ON CONFLICT(project_uid) DO UPDATE SET policy=excluded.policy',(project_uid,_json(policy.model_dump(mode='json'))))
        return self.get_config(project_uid)

    def configure_instance(self,instance_uid,policy):
        policy=ProcessingPolicy.model_validate(policy)
        with self.db.transaction() as c:
            if not c.execute('SELECT 1 FROM instances WHERE instance_uid=?',(instance_uid,)).fetchone():
                raise ProcessingError('INSTANCE_NOT_CONFIGURED')
            c.execute('INSERT INTO processing_instance_policies VALUES(?,?) ON CONFLICT(instance_uid) DO UPDATE SET policy=excluded.policy',(instance_uid,_json(policy.model_dump(mode='json'))))
        return {'instance_uid':instance_uid,'policy':policy.model_dump(mode='json')}

    def _config(self,project_uid,c):
        row=c.execute('SELECT p.project_uid,p.instance_uid,p.source_project_id,i.source_type FROM projects p JOIN instances i USING(instance_uid) WHERE project_uid=?',(project_uid,)).fetchone()
        if row is None:raise ProcessingError('PROJECT_NOT_CONFIGURED')
        result=dict(row)
        policies=[]
        for table,column,uid in [('processing_instance_policies','instance_uid',row['instance_uid']),('processing_project_policies','project_uid',project_uid)]:
            policy=c.execute(f'SELECT policy FROM {table} WHERE {column}=?',(uid,)).fetchone()
            policies.append(ProcessingPolicy.model_validate_json(policy[0]) if policy else ProcessingPolicy())
        effective={'fields':[{'kind':'NORMALIZED','key':'title'},{'kind':'NORMALIZED','key':'description'}], 'scope_fields':{},'chunking':ChunkConfig().model_dump(mode='json')}
        for policy in policies:
            if policy.fields is not None:effective['fields']=[x.model_dump() for x in policy.fields]
            effective['scope_fields'].update({k:[x.model_dump() for x in v] for k,v in policy.scope_fields.items()})
            if policy.chunking is not None:effective['chunking']=policy.chunking.model_dump(mode='json')
        result.update(instance_policy=policies[0].model_dump(mode='json'),policy=policies[1].model_dump(mode='json'),effective_policy=effective)
        result['config_revision']=fingerprint(result)
        return result

    def get_config(self,project_uid):
        with self.db.connect() as c:return self._config(project_uid,c)

    def _runtime(self,project_uid,runtime=None):
        if runtime is None:runtime=self.runtime_factory(project_uid)
        if runtime is None:raise ProcessingError('MODEL_PROFILE_UNCONFIGURED')
        profile=runtime.profile or runtime.verify_runtime()
        if not isinstance(profile,dict):raise ProcessingError('MODEL_RUNTIME_UNVERIFIED')
        if profile.get('state')!='VERIFIED' and not (self.allow_fixture and profile.get('state')=='FIXTURE_ONLY'):
            raise ProcessingError('MODEL_RUNTIME_UNVERIFIED')
        if profile.get('tokenizer_id')!=runtime.tokenizer.identity or profile.get('config')!=runtime.config.model_dump() or profile.get('model_digest')!=runtime.config.expected_digest:
            raise ProcessingError('MODEL_RUNTIME_DRIFT')
        body={k:v for k,v in profile.items() if k!='fingerprint'}
        if profile.get('fingerprint')!=fingerprint(body):raise ProcessingError('MODEL_PROFILE_CORRUPT')
        return runtime,profile

    @staticmethod
    def _refs(c,project_uid):
        return [dict(row) for row in c.execute("SELECT i.item_uid,i.source_item_id,s.latest_revision_uid AS revision_uid,m.scope_id FROM items i JOIN item_collection_state s USING(item_uid) JOIN collection_memberships m ON m.project_uid=i.project_uid AND m.source_item_id=i.source_item_id WHERE i.project_uid=? AND m.state='IN_SCOPE' AND i.deleted_state='active' ORDER BY i.item_uid",(project_uid,))]

    @staticmethod
    def _item_policy(snapshot,ref):
        effective=snapshot['config']['effective_policy']
        fields=effective['scope_fields'].get(ref['scope_id'],effective['fields'])
        policy={'fields':fields,'chunking':snapshot['chunking'],'model_fingerprint':snapshot['model_fingerprint'], **snapshot['processor_versions']}
        return policy,fingerprint(policy)

    def _prepare(self,project_uid):
        runtime,profile=self._runtime(project_uid)
        with self.db.connect() as c:
            config=self._config(project_uid,c)
            refs=self._refs(c,project_uid)
        chunking=dict(config['effective_policy']['chunking'])
        chunking['effective_max_input_tokens']=min(chunking['effective_max_input_tokens'],runtime.config.effective_max_input_tokens)
        try:chunking=ChunkConfig.model_validate(chunking).model_dump(mode='json')
        except ValueError:raise ProcessingError('CHUNK_CONFIG_MODEL_BUDGET_INVALID') from None
        snapshot={'project_uid':project_uid,'config':config,'refs':refs,'chunking':chunking,'model_fingerprint':profile['fingerprint'],'runtime_profile':profile,'processor_versions':{'normalizer':NORMALIZER_VERSION,'chunker':CHUNKER_VERSION,'tables':TABLE_SERIALIZATION_VERSION}}
        revision=fingerprint(snapshot)
        with self.db.connect() as c:
            ready=all(c.execute('SELECT 1 FROM processing_results WHERE revision_uid=? AND policy_fingerprint=?',(ref['revision_uid'],self._item_policy(snapshot,ref)[1])).fetchone() for ref in refs)
        pre={'status':'READY','process_ready':True,'embed_ready':ready,'sync_ready':False,'estimated_items':len(refs),'config_revision':revision,'diagnostics':[] if ready else ['PROCESS_REQUIRED']}
        return pre,snapshot

    def preflight(self,project_uid):
        try:return self._prepare(project_uid)[0]
        except (LeaseLost,sqlite3.Error):raise
        except Exception as error:
            return {'status':'BLOCKED','process_ready':False,'embed_ready':False,'sync_ready':False,'estimated_items':None,'config_revision':None,'diagnostics':[getattr(error,'code','PROCESSING_PREFLIGHT_FAILED')]}

    def enqueue(self,project_uid,stage='PROCESS',config_revision=None):
        if stage not in {'PROCESS','EMBED'}:raise ProcessingError('STAGE_NOT_IMPLEMENTED')
        pre,snapshot=self._prepare(project_uid)
        if config_revision is not None and config_revision!=pre['config_revision']:raise ProcessingError('STALE_PREFLIGHT')
        if stage=='EMBED' and not pre['embed_ready']:raise ProcessingError('PROCESS_REQUIRED')
        job_id=str(uuid.uuid4());now=time.time()
        with self.db.transaction() as c:
            if self._config(project_uid,c)!=snapshot['config'] or self._refs(c,project_uid)!=snapshot['refs']:
                raise ProcessingError('STALE_PREFLIGHT')
            c.execute('INSERT INTO jobs(job_id,project_uid,stage,created_at,updated_at,progress_total) VALUES(?,?,?,?,?,?)',(job_id,project_uid,stage,now,now,len(snapshot['refs'])))
            c.execute('INSERT INTO processing_snapshots VALUES(?,?,?)',(job_id,pre['config_revision'],_json(snapshot)))
            Queue._event(c,job_id,'QUEUED',now)
            return Queue._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone())

    @staticmethod
    def _guard(c,job):Queue._guard(c,job['job_id'],job['fencing_token'],time.time())

    def _live(self,job,abort_check):
        with self.db.transaction() as c:self._guard(c,job)
        if abort_check():raise ProcessingError('ABORT_REQUESTED',stop_state='PAUSED')

    def _snapshot(self,job):
        with self.db.connect() as c:row=c.execute('SELECT config_revision,snapshot FROM processing_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()
        if row is None:raise ProcessingError('PROCESSING_SNAPSHOT_MISSING')
        snapshot=json.loads(row['snapshot'])
        if snapshot['project_uid']!=job['project_uid'] or fingerprint(snapshot)!=row['config_revision']:
            raise ProcessingError('SNAPSHOT_INTEGRITY_ERROR')
        return snapshot

    @staticmethod
    def _field(envelope,ref):
        if ref['kind']=='NORMALIZED':
            key=ref['key']
            if key not in envelope:raise ProcessingError('SELECTED_FIELD_MISSING',False)
            value=envelope[key]
            if key=='description':
                if not isinstance(value,dict):raise ProcessingError('FIELD_VALUE_UNSUPPORTED',False)
                if value.get('html') is not None:return value['html'],'text/html'
                return value.get('raw'),value.get('format','text/plain')
            return value,'text/plain'
        fields=[f for f in envelope['fields'] if f.get('source_field_id')==ref['key']]
        if not fields:raise ProcessingError('SELECTED_FIELD_MISSING',False)
        if len(fields)!=1:raise ProcessingError('DUPLICATE_SOURCE_FIELD',False)
        return fields[0].get('raw_value'),fields[0].get('source_format') or 'text/plain'

    def _result(self,revision_uid,policy_fingerprint):
        with self.db.connect() as c:
            row=c.execute('SELECT * FROM processing_results WHERE revision_uid=? AND policy_fingerprint=?',(revision_uid,policy_fingerprint)).fetchone()
            return dict(row) if row else None

    def _process(self,job,snapshot,ref,runtime,abort_check):
        policy,policy_hash=self._item_policy(snapshot,ref)
        existing=self._result(ref['revision_uid'],policy_hash)
        if existing:return existing['result_uid']
        with self.db.connect() as c:
            row=c.execute('SELECT raw_payload FROM item_revisions WHERE revision_uid=? AND item_uid=?',(ref['revision_uid'],ref['item_uid'])).fetchone()
        if row is None:raise ProcessingError('PINNED_REVISION_MISSING')
        envelope=json.loads(row[0]); artifacts=[]
        for selected in policy['fields']:
            self._live(job,abort_check)
            value,source_format=self._field(envelope,selected)
            document=normalize_field(value,source_format)
            field_id=('normalized:' if selected['kind']=='NORMALIZED' else 'source:')+selected['key']
            chunks=make_chunks(document,title=envelope.get('title',''),field_id=field_id,tokenizer=runtime.tokenizer,config=ChunkConfig.model_validate(snapshot['chunking']),model_fingerprint=snapshot['model_fingerprint'])
            artifacts.append((selected,field_id,source_format,document,chunks))
        result_uid=canonical_uid('processing-result',ref['revision_uid'],policy_hash)
        config=snapshot['config'];scope_kind='TRACKER' if config['source_type']=='codebeamer' else 'WORK_ITEM_TYPE'
        with self.db.transaction() as c:
            self._guard(c,job)
            c.execute('INSERT INTO processing_results VALUES(?,?,?,?,?,?,?,?)',(result_uid,job['project_uid'],ref['item_uid'],ref['revision_uid'],policy_hash,snapshot['model_fingerprint'],'PROCESS_READY',_json({'policy':policy,'diagnostics':[d for a in artifacts for d in a[3]['diagnostics']]})))
            for selected,field_id,source_format,document,chunks in artifacts:
                normalized=selected['kind']=='NORMALIZED'
                source_id=field_id if normalized else selected['key']
                field_uid=canonical_uid('normalized-field',config['instance_uid'],config['source_project_id'],scope_kind,ref['scope_id'],source_id) if normalized else canonical_uid('field',config['instance_uid'],config['source_project_id'],scope_kind,ref['scope_id'],source_id)
                field_scope=_json([config['source_project_id'],scope_kind,ref['scope_id']])
                # Normalized namespace is structurally distinct from all source IDs.
                if normalized:field_scope=_json(['NORMALIZED',config['source_project_id'],scope_kind,ref['scope_id']])
                c.execute('INSERT INTO field_definitions(field_def_uid,instance_uid,scope,source_field_id,kind) VALUES(?,?,?,?,?) ON CONFLICT(field_def_uid) DO NOTHING',(field_uid,config['instance_uid'],field_scope,source_id,'normalized' if normalized else 'source'))
                block_ids={b['block_id']:canonical_uid(result_uid,field_id,b['block_id']) for b in document['blocks']}
                for b in document['blocks']:
                    c.execute('INSERT INTO content_blocks VALUES(?,?,?,?,?,?,?,?)',(block_ids[b['block_id']],ref['revision_uid'],field_uid,b['order'],b['kind'],b.get('raw_html'),_json(b['table']) if b.get('table') else None,b.get('text')))
                for chunk in chunks:
                    key=canonical_uid(result_uid,field_id,chunk['chunk_key'])
                    uid=canonical_uid('chunk',ref['revision_uid'],key)
                    c.execute('INSERT INTO chunks(chunk_uid,revision_uid,field_def_uid,block_uid,chunk_key,input_text,content_hash,model_fingerprint,input_tokens,source_span_offsets,row_ids,embedding_input_digest,tokenizer_id,effective_max_input_tokens) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid,ref['revision_uid'],field_uid,block_ids[chunk['block_id']],key,chunk['input_text'],chunk['content_hash'],snapshot['model_fingerprint'],chunk['input_tokens'],_json(chunk['source_span_offsets']),_json(chunk['row_ids']),hashlib.sha256(chunk['input_text'].encode()).hexdigest(),chunk['tokenizer_id'],chunk['effective_max_input_tokens']))
                    c.execute('INSERT INTO processing_membership VALUES(?,?)',(result_uid,uid))
        return result_uid

    @staticmethod
    def _vector(vector,dimension,code):
        if not isinstance(vector,list) or len(vector)!=dimension or any(isinstance(n,bool) or not isinstance(n,(float,int)) or not math.isfinite(n) for n in vector) or not any(vector):
            raise ProcessingError(code)
        return [float(n) for n in vector]

    def _embed(self,job,snapshot,ref,runtime,abort_check):
        result=self._result(ref['revision_uid'],self._item_policy(snapshot,ref)[1])
        if result is None:raise ProcessingError('PROCESS_REQUIRED')
        result_uid=result['result_uid'];dimension=runtime.config.vector_dimension
        with self.db.connect() as c:
            chunks=[dict(r) for r in c.execute('SELECT c.* FROM chunks c JOIN processing_membership m USING(chunk_uid) WHERE m.result_uid=? ORDER BY chunk_uid',(result_uid,))]
        for chunk in chunks:
            self._live(job,abort_check)
            if chunk['model_fingerprint']!=snapshot['model_fingerprint'] or chunk['tokenizer_id']!=runtime.tokenizer.identity or runtime.tokenizer.count(chunk['input_text'])!=chunk['input_tokens'] or chunk['input_tokens']>runtime.config.effective_max_input_tokens or hashlib.sha256(chunk['input_text'].encode()).hexdigest()!=chunk['embedding_input_digest']:
                raise ProcessingError('CHUNK_INTEGRITY_ERROR')
            key=(job['project_uid'],chunk['content_hash'],snapshot['model_fingerprint'])
            with self.db.connect() as c:cached=c.execute('SELECT * FROM embedding_cache WHERE project_uid=? AND content_hash=? AND model_fingerprint=?',key).fetchone()
            if cached:
                try:vector=self._vector(json.loads(cached['vector_json']),dimension,'VECTOR_CACHE_CORRUPT')
                except (ValueError,TypeError):raise ProcessingError('VECTOR_CACHE_CORRUPT') from None
                if cached['dimension']!=dimension or fingerprint(vector)!=cached['vector_digest']:raise ProcessingError('VECTOR_CACHE_CORRUPT')
            else:
                vector=self._vector(runtime.embed(chunk['input_text'],expected_tokens=chunk['input_tokens']),dimension,'VECTOR_INTEGRITY_ERROR')
            self._live(job,abort_check)
            with self.db.transaction() as c:
                self._guard(c,job)
                if not cached:c.execute('INSERT INTO embedding_cache VALUES(?,?,?,?,?,?)',(*key,_json(vector),fingerprint(vector),dimension))
                c.execute('INSERT OR IGNORE INTO embedding_chunk_vectors VALUES(?,?,?,?,?)',(result_uid,chunk['chunk_uid'],*key))
        with self.db.transaction() as c:
            self._guard(c,job)
            count=c.execute('SELECT count(*) FROM embedding_chunk_vectors WHERE result_uid=?',(result_uid,)).fetchone()[0]
            if count!=len(chunks):raise ProcessingError('EMBEDDING_INCOMPLETE')
            c.execute('INSERT INTO embedding_manifests VALUES(?,?,?,?) ON CONFLICT(result_uid) DO UPDATE SET manifest_digest=excluded.manifest_digest,chunk_count=excluded.chunk_count',(result_uid,snapshot['model_fingerprint'],len(chunks),fingerprint([(x['chunk_uid'],x['content_hash']) for x in chunks])))
            c.execute("UPDATE processing_results SET state='EMBED_READY' WHERE result_uid=?",(result_uid,))
        return result_uid

    def _outcome(self,job,ref,result_uid=None,error=None):
        with self.db.transaction() as c:
            self._guard(c,job)
            state='FAILED' if error else 'SUCCEEDED'
            c.execute('INSERT INTO processing_outcomes VALUES(?,?,?,?,?,?)',(job['job_id'],ref['item_uid'],ref['revision_uid'],result_uid,state,error))
            if error:
                c.execute('INSERT INTO failed_items(failed_item_uid,job_id,project_uid,item_uid,revision_uid,failed_stage,error_class,retryable) VALUES(?,?,?,?,?,?,?,1)',(canonical_uid(job['job_id'],ref['item_uid'],job['stage']),job['job_id'],job['project_uid'],ref['item_uid'],ref['revision_uid'],job['stage'],error))
            counts=dict(c.execute('SELECT state,count(*) FROM processing_outcomes WHERE job_id=? GROUP BY state',(job['job_id'],)).fetchall())
            c.execute('UPDATE jobs SET succeeded_items=?,failed_items=?,checkpoint=?,updated_at=? WHERE job_id=?',(counts.get('SUCCEEDED',0),counts.get('FAILED',0),_json({'last_item_uid':ref['item_uid'],'outcomes':sum(counts.values())}),time.time(),job['job_id']))

    def run(self,job,abort_check=lambda:False):
        runtime=None;previous_abort=None
        try:
            if job.get('stage') not in {'PROCESS','EMBED'}:raise ProcessingError('STAGE_NOT_IMPLEMENTED')
            self._live(job,abort_check)
            snapshot=self._snapshot(job)
            if snapshot['processor_versions']!={'normalizer':NORMALIZER_VERSION,'chunker':CHUNKER_VERSION,'tables':TABLE_SERIALIZATION_VERSION}:
                raise ProcessingError('PROCESSOR_VERSION_DRIFT')
            runtime=self.runtime_factory(job['project_uid'])
            if runtime is None:raise ProcessingError('MODEL_PROFILE_UNCONFIGURED')
            previous_abort=runtime.abort_check
            def runtime_abort():
                with self.db.transaction() as c:self._guard(c,job)
                return abort_check()
            runtime.abort_check=runtime_abort
            checked,profile=self._runtime(job['project_uid'],runtime)
            if profile['fingerprint']!=snapshot['model_fingerprint']:raise ProcessingError('MODEL_RUNTIME_DRIFT')
            for ref in snapshot['refs']:
                self._live(job,abort_check)
                with self.db.connect() as c:done=c.execute('SELECT 1 FROM processing_outcomes WHERE job_id=? AND item_uid=?',(job['job_id'],ref['item_uid'])).fetchone()
                if done:continue
                try:
                    result_uid=(self._process if job['stage']=='PROCESS' else self._embed)(job,snapshot,ref,runtime,abort_check)
                    self._live(job,abort_check)
                    self._outcome(job,ref,result_uid)
                except (LeaseLost,sqlite3.Error,OSError):raise
                except Exception as error:
                    if getattr(error,'global_error',True):raise
                    self._outcome(job,ref,error=getattr(error,'code','ITEM_PROCESSING_FAILED'))
            with self.db.connect() as c:failed=c.execute("SELECT count(*) FROM processing_outcomes WHERE job_id=? AND state='FAILED'",(job['job_id'],)).fetchone()[0]
            state='COMPLETED_WITH_ERRORS' if failed else 'SUCCEEDED'
            self.queue.finish(job['job_id'],job['fencing_token'],state)
            return state
        except LeaseLost:raise
        except Exception as error:
            state=getattr(error,'stop_state','BLOCKED')
            if state not in {'BLOCKED','PAUSED','FAILED','CANCELLED'}:state='BLOCKED'
            code='STORAGE_ERROR' if isinstance(error,(sqlite3.Error,OSError)) else getattr(error,'code','PROCESSING_FAILED')
            self.queue.finish(job['job_id'],job['fencing_token'],state,code)
            return state
        finally:
            if runtime is not None and previous_abort is not None:runtime.abort_check=previous_abort
