"""SRS-033/034: bounded project-owned golden evaluation and read-only integrity.

No external dataset loading or ALM calls. All durable outputs are lease-fenced.
"""
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid
from pydantic import BaseModel,ConfigDict,Field,model_validator
from almrag.embedding import fingerprint
from almrag.queue import Queue,LeaseLost
from almrag.storage import canonical_uid
from almrag.retrieval import SearchError
from almrag.search_filters import equal
from almrag.normalization import normalize_field,VERSION as NORMALIZER_VERSION
from almrag.processing import ProcessingService
from almrag.chunking import verify_source_coverage,CHUNKER_VERSION,TABLE_SERIALIZATION_VERSION


class QualityError(ValueError):
    def __init__(self,code,status=422):
        super().__init__(code);self.code,self.status=code,status


class GoldenCase(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    query:str=Field(min_length=1,max_length=65536)
    relevant_item_uids:list[str]=Field(min_length=1,max_length=1000)
    @model_validator(mode='after')
    def bounded(self):
        if not self.query.strip() or any(not x.strip() or len(x)>1024 for x in self.relevant_item_uids) or len(set(self.relevant_item_uids))!=len(self.relevant_item_uids):raise ValueError('nonblank unique references required')
        return self


class GoldenDataset(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    cases:list[GoldenCase]=Field(min_length=1,max_length=1000)


def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def metrics(ranked,relevant,k):
    ranked=list(dict.fromkeys(ranked))[:k];relevant=set(relevant)
    matches=[n for n,item in enumerate(ranked,1) if item in relevant]
    return {'precision_at_k':len(matches)/k,'recall_at_k':len(matches)/len(relevant) if relevant else 0.,'mrr':1./matches[0] if matches else 0.}


class QualityService:
    MAX_DATASET_BYTES=2*1024*1024
    MAX_ROWS=1000000
    def __init__(self,db,search_service=None,vector_store=None,attachment_root=None):
        self.db,self.search_service,self.vector_store=db,search_service,vector_store
        self.attachment_root=Path(attachment_root).resolve() if attachment_root else None
        self.queue=Queue(db)

    @staticmethod
    def _project(c,project):
        if not c.execute('SELECT 1 FROM projects WHERE project_uid=?',(project,)).fetchone():raise QualityError('NOT_FOUND',404)

    @staticmethod
    def _owners(c,project,dataset):
        for case in dataset['cases']:
            for item in case['relevant_item_uids']:
                row=c.execute('SELECT project_uid FROM items WHERE item_uid=?',(item,)).fetchone()
                if row is None or row[0]!=project:raise QualityError('DATASET_ITEM_SCOPE',403)

    def stage_dataset(self,project,payload):
        payload=GoldenDataset.model_validate(payload).model_dump();encoded=_json(payload)
        if len(encoded.encode())>self.MAX_DATASET_BYTES:raise QualityError('DATASET_TOO_LARGE',413)
        ref=str(uuid.uuid4());sha=hashlib.sha256(encoded.encode()).hexdigest()
        with self.db.transaction() as c:
            self._project(c,project);self._owners(c,project,payload)
            c.execute('INSERT INTO quality_datasets VALUES(?,?,?,?,?,?)',(ref,project,encoded,sha,len(payload['cases']),time.time()))
        return {'dataset_ref':ref,'project_uid':project,'case_count':len(payload['cases']),'sha256':sha}

    def _dataset(self,c,project,ref):
        row=c.execute('SELECT * FROM quality_datasets WHERE dataset_ref=? AND project_uid=?',(ref,project)).fetchone()
        if row is None:raise QualityError('NOT_FOUND',404)
        if hashlib.sha256(row['payload'].encode()).hexdigest()!=row['sha256']:raise QualityError('DATASET_INTEGRITY_ERROR')
        payload=GoldenDataset.model_validate_json(row['payload']).model_dump();self._owners(c,project,payload)
        return payload

    def _enqueue(self,project,stage,snapshot):
        now=time.time();job=str(uuid.uuid4())
        with self.db.transaction() as c:
            self._project(c,project)
            if stage=='EVALUATE':self._dataset(c,project,snapshot['dataset_ref'])
            c.execute('INSERT INTO jobs(job_id,project_uid,stage,created_at,updated_at) VALUES(?,?,?,?,?)',(job,project,stage,now,now))
            c.execute('INSERT INTO quality_requests VALUES(?,?,?)',(job,_json(snapshot),fingerprint(snapshot)))
            Queue._event(c,job,'QUEUED',now)
        return self.queue.get_job(job)

    def enqueue_integrity(self,project):return self._enqueue(project,'INTEGRITY',{})

    def enqueue_evaluation(self,project,dataset_ref,methods=None,top_k=10):
        methods=['dense','keyword','hybrid'] if methods is None else methods
        if not isinstance(methods,list) or not methods or len(set(methods))!=len(methods) or any(m not in ('dense','keyword','hybrid') for m in methods) or type(top_k) is not int or not 1<=top_k<=100:raise QualityError('EVALUATION_REQUEST_INVALID')
        return self._enqueue(project,'EVALUATE',{'dataset_ref':dataset_ref,'methods':methods,'top_k':top_k})

    @staticmethod
    def _refs(c,project):
        row=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(project,)).fetchone()
        if row is None or not row[0]:raise QualityError('INDEX_NOT_READY',409)
        # Active revisions are part of the comparison pin, even during same-generation item publication.
        revisions=[tuple(r) for r in c.execute('SELECT item_uid,active_revision_uid,deleted_state FROM items WHERE project_uid=? ORDER BY item_uid',(project,))]
        memberships=[tuple(r) for r in c.execute('SELECT source_item_id,scope_id,state FROM collection_memberships WHERE project_uid=? ORDER BY source_item_id',(project,))]
        selection=c.execute('SELECT config_revision FROM project_selections WHERE project_uid=?',(project,)).fetchone()
        return row[0],fingerprint({'items':revisions,'memberships':memberships,'selection':selection[0] if selection else None})

    def _evaluate(self,project,snapshot,live):
        if self.search_service is None:raise QualityError('SEARCH_RUNTIME_UNCONFIGURED',409)
        with self.db.connect() as c:
            dataset=self._dataset(c,project,snapshot['dataset_ref']);pinned=self._refs(c,project)
        results={}
        def guard():
            live()
            with self.db.connect() as c:
                try:current=self._refs(c,project)
                except QualityError:raise QualityError('EVALUATION_GENERATION_DRIFT',409) from None
            if current!=pinned:raise QualityError('EVALUATION_GENERATION_DRIFT',409)
        for method in snapshot['methods']:
            cases=[]
            for case in dataset['cases']:
                guard()
                response=self.search_service.search({'query':case['query'],'project_uids':[project],'top_k':snapshot['top_k'],'response':{'include_matched_chunks':False}},allowed_projects=[project],method=method)
                guard()
                if response.get('unindexed_project_uids') or response.get('backfill_limited'):raise QualityError('EVALUATION_RETRIEVAL_INCOMPLETE',409)
                cases.append(metrics([r['item_uid'] for r in response['results']],case['relevant_item_uids'],snapshot['top_k']))
            results[method]={key:sum(case[key] for case in cases)/len(cases) for key in cases[0]}
            results[method]['case_count']=len(cases)
        return 'PASS',{'methods':results,'generation_refs':{project:pinned[0]},'snapshot_fingerprint':pinned[1],'top_k':snapshot['top_k'],'case_count':len(dataset['cases']),'exact_id_boost':'hybrid-only metadata boost; dense/keyword pure channels','quality_target':'NO_FIXED_THRESHOLD','model_quality':'NOT VERIFIED unless dataset and runtime independently calibrated'}

    @staticmethod
    def _derived_integrity(c,result,live):
        """Reconstruct transformations from immutable originals without a model call."""
        errors={'TRANSFORMATION_CONTENT':0,'SOURCE_SPAN_COVERAGE':0,'CHUNK_CONTENT_HASH':0}
        raw=c.execute('SELECT raw_payload FROM item_revisions WHERE revision_uid=?',(result['revision_uid'],)).fetchone()
        envelope=json.loads(raw[0]);policy=json.loads(result['metadata'])['policy']
        if fingerprint(policy)!=result['policy_fingerprint']:
            errors['TRANSFORMATION_CONTENT']+=1
        if (policy.get('normalizer'),policy.get('chunker'),policy.get('tables'))!=(NORMALIZER_VERSION,CHUNKER_VERSION,TABLE_SERIALIZATION_VERSION):
            return errors,True
        chunks=[dict(row) for row in c.execute('SELECT c.* FROM chunks c JOIN processing_membership m USING(chunk_uid) WHERE m.result_uid=?',(result['result_uid'],))]
        expected_ids=set()
        for selected in policy['fields']:
            live()
            value,source_format=ProcessingService._field(envelope,selected)
            document=normalize_field(value,source_format)
            field_id=('normalized:' if selected['kind']=='NORMALIZED' else 'source:')+selected['key']
            block_ids={b['block_id']:canonical_uid(result['result_uid'],field_id,b['block_id']) for b in document['blocks']}
            expected_ids.update(block_ids.values())
            for block in document['blocks']:
                row=c.execute('SELECT b.*,d.source_field_id FROM content_blocks b LEFT JOIN field_definitions d USING(field_def_uid) WHERE b.revision_uid=? AND b.block_uid=?',(result['revision_uid'],block_ids[block['block_id']])).fetchone()
                source_id=field_id if selected['kind']=='NORMALIZED' else selected['key']
                if row is None or row['source_field_id']!=source_id or row['block_order']!=block['order'] or row['type']!=block['kind'] or row['normalized_text']!=block.get('text') or row['raw_html']!=block.get('raw_html') or not equal(json.loads(row['table_json']) if row['table_json'] else None,block.get('table')):
                    errors['TRANSFORMATION_CONTENT']+=1
            field_chunks=[x for x in chunks if x['block_uid'] in block_ids.values()]
            restored=[{**x,'source_span_offsets':json.loads(x['source_span_offsets'])} for x in field_chunks]
            try:verify_source_coverage(document,restored)
            except (ValueError,KeyError,TypeError):errors['SOURCE_SPAN_COVERAGE']+=1
            for chunk in field_chunks:
                digest=fingerprint({'config':policy['chunking'],'model':result['model_fingerprint'],'tokenizer':chunk['tokenizer_id'],'normalizer_version':policy['normalizer'],'chunker_version':policy['chunker'],'table_version':policy['tables'],'input_text':chunk['input_text']})
                if digest!=chunk['content_hash']:errors['CHUNK_CONTENT_HASH']+=1
                block=next(b for b in document['blocks'] if block_ids[b['block_id']]==chunk['block_uid'])
                row_ids=json.loads(chunk['row_ids'])
                if block['kind']=='table':
                    allowed={f'r{r}' for cell in block['table']['cells'] for r in range(cell['row'],cell['row']+cell['rowspan'])}
                    if not row_ids or any(r not in allowed for r in row_ids):errors['SOURCE_SPAN_COVERAGE']+=1
        if any(chunk['block_uid'] not in expected_ids for chunk in chunks):errors['TRANSFORMATION_CONTENT']+=1
        return errors,False

    def _integrity(self,project,live):
        checks=[];issues=[];issue_keys=set()
        def issue(code,item,revision):
            key=(code,item,revision)
            if key in issue_keys:return
            issue_keys.add(key)
            if len(issues)>=1000:return
            action='REBUILD_INDEX' if code in {'DENSE_COVERAGE','KEYWORD_COVERAGE','ACTIVE_PUBLICATIONS'} else 'RECOVER_TRUSTED_RAW_AND_REPROCESS'
            issues.append({'code':code,'item_uid':item,'revision_uid':revision,'recommended_action':action})
        def check(code,errors=0,state=None):checks.append({'code':code,'status':state or ('FAIL' if errors else 'PASS'),'errors':errors})
        with self.db.connect() as c:
            c.execute('BEGIN')
            self._project(c,project)
            rows=c.execute('SELECT r.* FROM item_revisions r JOIN items i USING(item_uid) WHERE i.project_uid=? LIMIT ?',(project,self.MAX_ROWS+1)).fetchall()
            if len(rows)>self.MAX_ROWS:raise QualityError('INTEGRITY_SCAN_LIMIT',409)
            chunk_count=c.execute('SELECT count(*) FROM chunks c JOIN item_revisions r USING(revision_uid) JOIN items i USING(item_uid) WHERE i.project_uid=?',(project,)).fetchone()[0]
            if chunk_count>self.MAX_ROWS:raise QualityError('INTEGRITY_SCAN_LIMIT',409)
            raw_errors=field_errors=attachment_errors=chunk_errors=0;attachment_unknown=False
            for row in rows:
                live()
                before=(raw_errors,field_errors,attachment_errors)
                try:
                    envelope=json.loads(row['raw_payload'])
                    attachments=c.execute('SELECT * FROM attachments WHERE revision_uid=?',(row['revision_uid'],)).fetchall()
                    checksums=[];used=set()
                    for index,metadata in enumerate(envelope.get('attachments',[])):
                        matches=[a for a in attachments if a['attachment_uid']==canonical_uid('attachment',project,str(envelope['id']),fingerprint(envelope),str(metadata.get('id',index)),a['checksum'])]
                        if len(matches)!=1:attachment_errors+=1;continue
                        used.add(matches[0]['attachment_uid']);checksums.append(matches[0]['checksum'])
                    if len(used)!=len(attachments):attachment_errors+=1
                    expected=fingerprint({'envelope':envelope,'attachment_checksums':checksums})
                    if row['hash']!=expected:raw_errors+=1
                    source_fields={str(x['source_field_id']):x for x in envelope.get('fields',[])}
                    seen_fields=set()
                    for field in c.execute('SELECT v.*,d.source_field_id,d.kind FROM field_values v JOIN field_definitions d USING(field_def_uid) WHERE revision_uid=?',(row['revision_uid'],)):
                        if field['kind']!='normalized':
                            seen_fields.add(field['source_field_id'])
                            original=source_fields.get(field['source_field_id'])
                            if original is None or not equal(json.loads(field['raw_value']),original.get('raw_value')):field_errors+=1
                    if seen_fields!=set(source_fields):field_errors+=1
                    for attachment in attachments:
                        if attachment['download_status']!='DOWNLOADED':attachment_errors+=1;continue
                        if self.attachment_root is None:attachment_unknown=True;continue
                        path=(self.attachment_root/attachment['disk_path']).resolve()
                        if not path.is_relative_to(self.attachment_root) or not path.is_file() or path.stat().st_size>64*1024*1024 or hashlib.sha256(path.read_bytes()).hexdigest()!=attachment['checksum']:attachment_errors+=1
                except (ValueError,TypeError,KeyError,OSError):raw_errors+=1
                for code,old,new in zip(('RAW_HASH','SOURCE_FIELD_VALUES','ATTACHMENTS'),before,(raw_errors,field_errors,attachment_errors)):
                    if new>old:issue(code,row['item_uid'],row['revision_uid'])
            for chunk in c.execute('SELECT c.* FROM chunks c JOIN item_revisions r USING(revision_uid) JOIN items i USING(item_uid) WHERE i.project_uid=?',(project,)):
                live()
                before=chunk_errors
                if chunk['input_tokens']>chunk['effective_max_input_tokens'] or chunk['truncation_detected'] or hashlib.sha256(chunk['input_text'].encode()).hexdigest()!=chunk['embedding_input_digest']:chunk_errors+=1
                try:
                    spans=json.loads(chunk['source_span_offsets']);row_ids=json.loads(chunk['row_ids'])
                    if not isinstance(spans,list) or not isinstance(row_ids,list):chunk_errors+=1
                    block=c.execute('SELECT * FROM content_blocks WHERE revision_uid=? AND block_uid=?',(chunk['revision_uid'],chunk['block_uid'])).fetchone()
                    table=json.loads(block['table_json']) if block and block['table_json'] else None
                    for span in spans:
                        if block is None:chunk_errors+=1;continue
                        text=block['normalized_text'] or ''
                        if span.get('coordinate_space')=='normalized_cell':
                            cells=(table or {}).get('cells',[])
                            cell=next((cell for cell in cells if cell.get('cell_id')==span.get('cell_id')),None)
                            if cell is None:chunk_errors+=1;continue
                            text=cell.get('text','')
                        if type(span.get('char_start')) is not int or type(span.get('char_end')) is not int or not 0<=span['char_start']<=span['char_end']<=len(text):chunk_errors+=1
                        elif span.get('utf8_byte_start')!=len(text[:span['char_start']].encode()) or span.get('utf8_byte_end')!=len(text[:span['char_end']].encode()):chunk_errors+=1
                except (ValueError,TypeError,AttributeError):chunk_errors+=1
                if chunk_errors>before:
                    owner=c.execute('SELECT item_uid FROM item_revisions WHERE revision_uid=?',(chunk['revision_uid'],)).fetchone()[0]
                    issue('CHUNK_BOUNDS',owner,chunk['revision_uid'])
            missing=c.execute('SELECT count(*) FROM items i LEFT JOIN collection_memberships m ON m.project_uid=i.project_uid AND m.source_item_id=i.source_item_id LEFT JOIN item_collection_state s USING(item_uid) WHERE i.project_uid=? AND (m.source_item_id IS NULL OR s.item_uid IS NULL)',(project,)).fetchone()[0]
            check('RAW_HASH',raw_errors);check('SOURCE_FIELD_VALUES',field_errors);check('ATTACHMENTS',attachment_errors,'NOT VERIFIED' if attachment_unknown and not attachment_errors else None);check('CHUNK_BOUNDS',chunk_errors);check('LOCAL_MEMBERSHIP',missing)
            processing_errors=0;processing_count=0
            derived_errors={'TRANSFORMATION_CONTENT':0,'SOURCE_SPAN_COVERAGE':0,'CHUNK_CONTENT_HASH':0};derived_unknown=False
            for result in c.execute('SELECT * FROM processing_results WHERE project_uid=?',(project,)):
                processing_count+=1;live()
                try:
                    errors,unknown=self._derived_integrity(c,result,live)
                    derived_unknown|=unknown
                    for code,count in errors.items():
                        derived_errors[code]+=count
                        if count:issue(code,result['item_uid'],result['revision_uid'])
                except (ValueError,TypeError,KeyError):
                    derived_errors['TRANSFORMATION_CONTENT']+=1
                    issue('TRANSFORMATION_CONTENT',result['item_uid'],result['revision_uid'])
                members=c.execute('SELECT count(*) FROM processing_membership WHERE result_uid=?',(result['result_uid'],)).fetchone()[0]
                if result['state']=='EMBED_READY':
                    manifest=c.execute('SELECT chunk_count FROM embedding_manifests WHERE result_uid=?',(result['result_uid'],)).fetchone()
                    vectors=c.execute('SELECT count(*) FROM embedding_chunk_vectors WHERE result_uid=?',(result['result_uid'],)).fetchone()[0]
                    if manifest is None or manifest[0]!=members or vectors!=members:processing_errors+=1
            check('PROCESSING_COVERAGE',processing_errors,'NOT VERIFIED' if not processing_count and not processing_errors else None)
            for code,count in derived_errors.items():check(code,count,'NOT VERIFIED' if (derived_unknown or not processing_count) and not count else None)
            generation=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(project,)).fetchone()[0]
            if not generation:
                check('ACTIVE_PUBLICATIONS',state='NOT VERIFIED');check('KEYWORD_COVERAGE',state='NOT VERIFIED');check('DENSE_COVERAGE',state='NOT VERIFIED')
            else:
                config=c.execute('SELECT * FROM generation_configs WHERE generation_uid=?',(generation,)).fetchone()
                publications=c.execute('SELECT p.* FROM index_publications p JOIN items i USING(item_uid) WHERE p.generation_uid=? AND i.project_uid=?',(generation,project)).fetchall()
                active_errors=int(config is None or config['cleanup_state']!='ACTIVE')
                active_errors+=c.execute('SELECT count(*) FROM items i LEFT JOIN index_publications p ON p.item_uid=i.item_uid AND p.generation_uid=? AND p.revision_uid=i.active_revision_uid WHERE i.project_uid=? AND i.active_revision_uid IS NOT NULL AND p.item_uid IS NULL',(generation,project)).fetchone()[0]
                lex_errors=dense_errors=0;dense_unknown=self.vector_store is None
                for pub in publications:
                    before=(active_errors,lex_errors,dense_errors)
                    live();points=json.loads(pub['dense_evidence'])
                    memberships={r[0] for r in c.execute('SELECT chunk_uid FROM processing_membership WHERE result_uid=?',(pub['result_uid'],))}
                    if len(points)!=pub['point_count'] or {p['payload']['chunk_uid'] for p in points}!=memberships or fingerprint(points)!=pub['points_digest']:active_errors+=1
                    actual_points={r['point_uuid']:dict(r) for r in c.execute('SELECT p.* FROM index_points p JOIN chunks c USING(chunk_uid) JOIN processing_membership m USING(chunk_uid) WHERE p.generation_uid=? AND m.result_uid=?',(generation,pub['result_uid']))}
                    if set(actual_points)!={p['id'] for p in points} or any(actual_points[p['id']]['vector_status']!='READY' or actual_points[p['id']]['source_hash']!=p['payload']['content_hash'] for p in points if p['id'] in actual_points):active_errors+=1
                    docs=[dict(r) for r in c.execute('SELECT d.* FROM keyword_documents d JOIN processing_membership m USING(chunk_uid) WHERE d.generation_uid=? AND m.result_uid=? ORDER BY d.point_uuid',(generation,pub['result_uid']))]
                    if {r['point_uuid'] for r in docs}!={p['id'] for p in points} or fingerprint(docs)!=pub['lexical_digest']:lex_errors+=1
                    for doc in docs:
                        fts=c.execute('SELECT terms,project_uid,generation_uid FROM keyword_fts WHERE point_uuid=?',(doc['point_uuid'],)).fetchall()
                        if len(fts)!=1 or tuple(fts[0])!=(doc['terms'],project,generation):lex_errors+=1
                    if self.vector_store is not None and config is not None:
                        if not hasattr(self.vector_store,'retrieve'):dense_unknown=True;continue
                        try:
                            for start in range(0,len(points),256):
                                live();batch=points[start:start+256];found=self.vector_store.retrieve(config['collection_name'],[p['id'] for p in batch]);expected={p['id']:p for p in batch}
                                if len(found)!=len(batch) or {p['id'] for p in found}!=set(expected):dense_errors+=1;continue
                                for point in found:
                                    wanted=expected[point['id']];vector=point.get('vector')
                                    if point.get('payload')!=wanted['payload'] or not isinstance(vector,list) or len(vector)!=len(wanted['vector']) or any(isinstance(a,bool) or not isinstance(a,(int,float)) or not math.isfinite(a) or abs(a-b)>1e-5 for a,b in zip(vector,wanted['vector'])):dense_errors+=1
                        except (ValueError,OSError,KeyError,TypeError):dense_errors+=1
                    for code,old,new in zip(('ACTIVE_PUBLICATIONS','KEYWORD_COVERAGE','DENSE_COVERAGE'),before,(active_errors,lex_errors,dense_errors)):
                        if new>old:issue(code,pub['item_uid'],pub['revision_uid'])
                check('ACTIVE_PUBLICATIONS',active_errors);check('KEYWORD_COVERAGE',lex_errors);check('DENSE_COVERAGE',dense_errors,'NOT VERIFIED' if dense_unknown and not dense_errors else None)
            failures=[dict(r) for r in c.execute("SELECT failed_item_uid,job_id,item_uid,revision_uid,failed_stage,retryable,replay_state FROM failed_items WHERE project_uid=? AND replay_state!='RESOLVED' ORDER BY failed_item_uid LIMIT 1000",(project,))]
        check('LIVE_ALM_COMPLETENESS',state='NOT VERIFIED')
        status='FAIL' if any(x['status']=='FAIL' for x in checks) else 'NOT VERIFIED' if any(x['status']=='NOT VERIFIED' for x in checks) else 'PASS'
        return status,{'checks':checks,'revision_count':len(rows),'generation_refs':{project:generation},'read_only':True,'issues':issues,'issue_count':len(issue_keys),'issues_truncated':len(issue_keys)>len(issues),'failed_item_replays':failures,'repair_policy':'Explicit existing failed-Item retry or project rebuild; derived/original storage corruption requires trusted raw recovery and reprocessing, never automatic destructive repair.'}

    def run(self,job,abort_check=lambda:False):
        def live():
            if abort_check():raise QualityError('QUALITY_ABORTED',409)
            with self.db.connect() as c:Queue._guard(c,job['job_id'],job['fencing_token'],time.time())
        live()
        try:
            with self.db.connect() as c:
                row=c.execute('SELECT snapshot,snapshot_hash FROM quality_requests WHERE job_id=?',(job['job_id'],)).fetchone()
                if row is None:raise QualityError('QUALITY_SNAPSHOT_MISSING')
                snapshot=json.loads(row[0])
                if fingerprint(snapshot)!=row[1]:raise QualityError('QUALITY_SNAPSHOT_INTEGRITY')
            if job['stage']=='INTEGRITY':status,report=self._integrity(job['project_uid'],live)
            elif job['stage']=='EVALUATE':status,report=self._evaluate(job['project_uid'],snapshot,live)
            else:raise QualityError('QUALITY_STAGE_INVALID')
        except LeaseLost:raise
        except (QualityError,SearchError) as e:status,report='FAIL',{'error_code':e.code}
        except (ValueError,TypeError,KeyError,OSError,sqlite3.Error):status,report='FAIL',{'error_code':'QUALITY_INTEGRITY_ERROR'}
        live()
        with self.db.transaction() as c:
            Queue._guard(c,job['job_id'],job['fencing_token'],time.time())
            c.execute('INSERT OR REPLACE INTO quality_reports VALUES(?,?,?,?,?)',(job['job_id'],job['project_uid'],job['stage'],status,_json(report)))
            state='COMPLETED_WITH_ERRORS' if status=='FAIL' else 'SUCCEEDED';error='QUALITY_CHECK_FAILED' if status=='FAIL' else None;now=time.time()
            c.execute('UPDATE jobs SET state=?,last_error_code=?,owner=NULL,fencing_token=NULL,lease_expires_at=NULL,updated_at=? WHERE job_id=?',(state,error,now,job['job_id']))
            Queue._event(c,job['job_id'],state,now,error)

    def report(self,job_id):
        with self.db.connect() as c:
            job=c.execute('SELECT 1 FROM jobs WHERE job_id=?',(job_id,)).fetchone()
            if job is None:raise QualityError('NOT_FOUND',404)
            row=c.execute('SELECT * FROM quality_reports WHERE job_id=?',(job_id,)).fetchone()
        if row is None:raise QualityError('REPORT_NOT_READY',409)
        result=dict(row);result['report']=json.loads(result['report']);return result
