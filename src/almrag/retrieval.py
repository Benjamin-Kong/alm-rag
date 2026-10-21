"""Authorized pair-filtered hybrid retrieval from one pinned SQLite read view."""
import json
import math
from almrag.embedding import fingerprint
from almrag.lexical import LexicalIndex,LEXICAL_VERSION
from almrag.search_filters import SearchFilters,matches
from almrag.readers import ReaderRegistry
from almrag.source_scope import allows_scope

from pydantic import BaseModel,ConfigDict,Field,model_validator


class SearchError(ValueError):
    def __init__(self,code,status=503):
        super().__init__(code);self.code,self.status,self.global_error=code,status,True


class ResponseOptions(BaseModel):
    model_config=ConfigDict(extra='forbid')
    include_full_item:bool=False
    include_matched_chunks:bool=True
    include_chunk_text:bool=False
    max_chunks_per_item:int=Field(default=2,ge=0,le=100)
    include_relations:bool=False
    include_attachments:bool=False
    include_scores:bool=True


class SearchRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query:str=Field(min_length=1,max_length=65536)
    project_uids:list[str]=Field(min_length=1,max_length=1000)
    top_k:int=Field(default=10,ge=1,le=100)
    response:ResponseOptions=Field(default_factory=ResponseOptions)
    filters:SearchFilters|None=None

    @model_validator(mode='after')
    def explicit_scope(self):
        if not self.query.strip() or any(not project for project in self.project_uids) or len(set(self.project_uids))!=len(self.project_uids):
            raise ValueError('explicit unique projects and nonblank query required')
        return self


class MatchedChunk(BaseModel):
    chunk_uid:str
    revision_uid:str
    field_def_uid:str|None=None
    block_uid:str|None=None
    source_span_offsets:list[dict]
    row_ids:list[str]
    input_text:str|None=None
    score:float|None=None


class SearchHit(BaseModel):
    item_uid:str
    project_uid:str
    revision_uid:str
    title:str
    score:float|None=None
    item:dict|None=None
    matched_chunks:list[MatchedChunk]|None=None
    relations:list[dict]|None=None
    attachments:list[dict]|None=None


class SearchResponse(BaseModel):
    total:int
    results:list[SearchHit]
    exhausted:bool
    backfill_limited:bool
    rounds:int
    unindexed_project_uids:list[str]


class ItemDetail(BaseModel):
    project_uid:str
    item_uid:str
    revision_uid:str
    source_revision:str
    item:dict
    content_blocks:list[dict]


class SearchService:
    def __init__(self,db,runtime_factory,vector_store,*,lexical=None,readers=None,allow_fixture=False,page_size=100,max_rounds=5):
        self.db,self.runtime_factory,self.vector_store=db,runtime_factory,vector_store
        self.allow_fixture,self.page_size,self.max_rounds=allow_fixture,page_size,max_rounds
        if type(page_size) is not int or not 1<=page_size<=1000 or type(max_rounds) is not int or not 1<=max_rounds<=20:
            raise ValueError('invalid retrieval budget')
        self.lexical=lexical or LexicalIndex(db)
        self.readers=readers or ReaderRegistry(db)

    @staticmethod
    def _authorize(projects,allowed):
        if not set(projects).issubset(set(allowed)):raise SearchError('FORBIDDEN',403)

    def _query_vector(self,project,profile,query):
        runtime=self.runtime_factory(project)
        if runtime is None:raise SearchError('MODEL_PROFILE_UNCONFIGURED',409)
        actual=runtime.profile or runtime.verify_runtime()
        if actual.get('state')!='VERIFIED' and not (self.allow_fixture and actual.get('state')=='FIXTURE_ONLY'):
            raise SearchError('MODEL_RUNTIME_UNVERIFIED',409)
        if actual!=profile or actual.get('fingerprint')!=fingerprint({k:v for k,v in actual.items() if k!='fingerprint'}) or actual.get('tokenizer_id')!=runtime.tokenizer.identity or actual.get('config')!=runtime.config.model_dump():
            raise SearchError('MODEL_RUNTIME_MISMATCH',409)
        count=runtime.tokenizer.count(query)
        if type(count) is not int or not 0<count<=runtime.config.effective_max_input_tokens:
            raise SearchError('QUERY_INPUT_TOO_LARGE',422)
        vector=runtime.embed(query,expected_tokens=count)
        if not isinstance(vector,list) or len(vector)!=runtime.config.vector_dimension or any(isinstance(n,bool) or not isinstance(n,(float,int)) or not math.isfinite(n) for n in vector) or not any(vector):
            raise SearchError('QUERY_VECTOR_INVALID')
        return vector

    @staticmethod
    def _candidate(c,point,project,generation):
        row=c.execute("""SELECT p.point_uuid,p.source_hash,c.*,r.item_uid,r.raw_payload,r.source_revision,
                i.project_uid,u.result_uid,u.dense_evidence,scope.scope_id
            FROM index_points p JOIN chunks c USING(chunk_uid)
            JOIN item_revisions r ON r.revision_uid=c.revision_uid
            JOIN items i ON i.item_uid=r.item_uid
            JOIN index_publications u ON u.generation_uid=p.generation_uid AND u.item_uid=i.item_uid AND u.revision_uid=c.revision_uid
            JOIN processing_membership m ON m.result_uid=u.result_uid AND m.chunk_uid=c.chunk_uid
            JOIN collection_memberships scope ON scope.project_uid=i.project_uid AND scope.source_item_id=i.source_item_id
            WHERE p.point_uuid=? AND p.generation_uid=? AND p.vector_status='READY' AND i.project_uid=?
                AND i.active_revision_uid=c.revision_uid AND i.deleted_state NOT IN ('deleted','unauthorized')
                AND scope.state IN ('IN_SCOPE','MISSING')""",(point['id'],generation,project)).fetchone()
        if row is None or not allows_scope(c,project,row['scope_id']):return None
        row=dict(row)
        expected={'project_uid':project,'generation_uid':generation,'item_uid':row['item_uid'],'revision_uid':row['revision_uid'],'chunk_uid':row['chunk_uid']}
        payload=point.get('payload')
        if not isinstance(payload,dict) or any(payload.get(k)!=v for k,v in expected.items()):
            raise SearchError('CANDIDATE_SCOPE_MISMATCH')
        evidence=json.loads(row['dense_evidence'])
        prepared=next((p for p in evidence if p['id']==point['id']),None)
        if prepared is None or row['source_hash']!=row['content_hash']:
            raise SearchError('MANIFEST_INTEGRITY_ERROR')
        prepared_payload=prepared['payload']
        if any(prepared_payload.get(k)!=v for k,v in expected.items()) or prepared_payload.get('result_uid')!=row['result_uid'] or prepared_payload.get('content_hash')!=row['content_hash'] or prepared_payload.get('model_fingerprint')!=row['model_fingerprint']:
            raise SearchError('MANIFEST_INTEGRITY_ERROR')
        if any(k not in prepared_payload or prepared_payload[k]!=v for k,v in payload.items()):
            raise SearchError('CANDIDATE_INTEGRITY_ERROR')
        return row

    @staticmethod
    def _raw(row):
        envelope=json.loads(row['raw_payload'])
        if not isinstance(envelope,dict):raise SearchError('SOURCE_INTEGRITY_ERROR')
        return envelope

    @staticmethod
    def _relations(c,revision,allowed):
        result=[]
        for row in c.execute('SELECT * FROM relations WHERE revision_uid=? ORDER BY relation_uid',(revision,)):
            target=row['target_uid']
            if target is not None:
                owner=c.execute('SELECT project_uid FROM items WHERE item_uid=?',(target,)).fetchone()
                if owner is None or owner[0] not in allowed:target=None
            result.append({'original_relation_type':row['original_relation_type'],'source_target_id':row['source_target_id'],'target_uid':target})
        return result

    @staticmethod
    def _attachments(c,revision):
        return [dict(row) for row in c.execute('SELECT filename,checksum,download_status FROM attachments WHERE revision_uid=? ORDER BY attachment_uid',(revision,))]

    def _restore(self,c,row,ranked,options,allowed):
        envelope=self._raw(row)
        hit={'item_uid':row['item_uid'],'project_uid':row['project_uid'],'revision_uid':row['revision_uid'],'title':envelope.get('title','')}
        if options.include_scores:hit['score']=max(score for _,score,_ in ranked)
        if options.include_full_item:hit['item']=envelope
        if options.include_matched_chunks:
            hit['matched_chunks']=[]
            real_chunks=[entry for entry in ranked if not entry[2].get('metadata_only')]
            for _,score,chunk in real_chunks[:options.max_chunks_per_item]:
                match={'chunk_uid':chunk['chunk_uid'],'revision_uid':chunk['revision_uid'],'field_def_uid':chunk['field_def_uid'],'block_uid':chunk['block_uid'],'source_span_offsets':json.loads(chunk['source_span_offsets']),'row_ids':json.loads(chunk['row_ids'])}
                if options.include_chunk_text:match['input_text']=chunk['input_text']
                if options.include_scores:match['score']=score
                hit['matched_chunks'].append(match)
        if options.include_relations:hit['relations']=self._relations(c,row['revision_uid'],allowed)
        if options.include_attachments:hit['attachments']=self._attachments(c,row['revision_uid'])
        return hit

    @staticmethod
    def _eligible(c,project,generation,filters,query):
        predicate='' if filters is not None else ' AND (i.source_item_id=? OR i.item_uid=?)'
        parameters=[] if filters is not None else [query,query]
        rows=c.execute("""SELECT i.item_uid,i.project_uid,i.source_item_id,r.revision_uid,r.source_revision,r.raw_payload,m.scope_id
            FROM items i JOIN item_revisions r ON r.revision_uid=i.active_revision_uid
            JOIN index_publications p ON p.item_uid=i.item_uid AND p.revision_uid=r.revision_uid AND p.generation_uid=?
            JOIN collection_memberships m ON m.project_uid=i.project_uid AND m.source_item_id=i.source_item_id
            WHERE i.project_uid=? AND i.deleted_state NOT IN ('deleted','unauthorized') AND m.state IN ('IN_SCOPE','MISSING')
            """+predicate+' ORDER BY i.item_uid',(generation,project,*parameters))
        result=[]
        for row in rows:
            if allows_scope(c,project,row['scope_id']) and matches(filters,row):
                result.append(dict(row))
                if filters is not None and len(result)>10000:raise SearchError('FILTER_TOO_BROAD',422)
        return result

    def search(self,payload,*,allowed_projects,method="hybrid"):
        if method not in {"dense","keyword","hybrid"}:raise ValueError("invalid search method")
        payload=SearchRequest.model_validate(payload)
        self._authorize(payload.project_uids,allowed_projects)
        with self.readers.snapshot(payload.project_uids) as (c,pairs):
            plans={};vectors={};candidates={};scores={};seen={};exhausted={};allowlists={};exact=set()
            for project,generation in pairs.items():
                config=c.execute('SELECT * FROM generation_configs WHERE generation_uid=?',(generation,)).fetchone()
                if config is None or config['cleanup_state']!='ACTIVE':raise SearchError('INDEX_NOT_READY',409)
                if config['lexical_version']!=LEXICAL_VERSION:raise SearchError('REBUILD_REQUIRED',409)
                eligible=self._eligible(c,project,generation,payload.filters,payload.query)
                if payload.filters is not None:allowlists[project]=[row['item_uid'] for row in eligible]
                for item in eligible:
                    if method!='hybrid' or payload.query not in {item['source_item_id'],item['item_uid']}:continue
                    point=c.execute("SELECT p.point_uuid FROM index_publications u CROSS JOIN processing_membership m ON m.result_uid=u.result_uid CROSS JOIN index_points p ON p.generation_uid=u.generation_uid AND p.chunk_uid=m.chunk_uid WHERE u.item_uid=? AND u.generation_uid=? AND p.vector_status='READY' ORDER BY p.point_uuid LIMIT 1",(item['item_uid'],generation)).fetchone()
                    if point:
                        evidence=c.execute('SELECT dense_evidence FROM index_publications WHERE item_uid=? AND generation_uid=?',(item['item_uid'],generation)).fetchone()
                        prepared=next((p for p in json.loads(evidence[0]) if p['id']==point[0]),None)
                        if prepared is None:raise SearchError('MANIFEST_INTEGRITY_ERROR')
                        row=self._candidate(c,prepared,project,generation)
                        if row is not None:
                            candidates[point[0]]=row;scores[point[0]]=1.0;exact.add(item['item_uid'])
                    else:
                        publication=c.execute("SELECT u.point_count,u.dense_evidence,r.state,(SELECT count(*) FROM processing_membership m WHERE m.result_uid=u.result_uid) AS members FROM index_publications u JOIN processing_results r ON r.result_uid=u.result_uid AND r.item_uid=u.item_uid AND r.revision_uid=u.revision_uid AND r.project_uid=? WHERE u.item_uid=? AND u.generation_uid=? AND u.revision_uid=?",(project,item['item_uid'],generation,item['revision_uid'])).fetchone()
                        if publication is None or publication['point_count']!=0 or json.loads(publication['dense_evidence'])!=[] or publication['members']!=0 or publication['state']!='EMBED_READY':raise SearchError('MANIFEST_INTEGRITY_ERROR')
                        key='metadata:'+item['item_uid'];candidates[key]={**item,'metadata_only':True};scores[key]=1.0;exact.add(item['item_uid'])
                if payload.filters is not None and not allowlists[project]:continue
                profile=json.loads(config['model_profile'])
                if method!='keyword':vectors[project]=self._query_vector(project,profile,payload.query)
                plans[project]=(generation,config['collection_name'])
            rounds=0
            for round_number in range(self.max_rounds):
                rounds=round_number+1
                for project,(generation,collection) in plans.items():
                    for channel in ({'dense':('dense',),'keyword':('lexical',),'hybrid':('dense','lexical')}[method]):
                        key=(project,channel)
                        if exhausted.get(key):continue
                        offset=round_number*self.page_size
                        options={} if project not in allowlists else {'item_uids':allowlists[project]}
                        if channel=='dense':
                            page=self.vector_store.query(collection,vectors[project],project_uid=project,generation_uid=generation,limit=self.page_size,offset=offset,**options)
                        else:page=self.lexical.search(project,generation,payload.query,self.page_size,offset,c=c,**options)
                        exhausted[key]=len(page)<self.page_size
                        for position,point in enumerate(page,offset+1):
                            pid=point['id']
                            prior=seen.setdefault(key,set())
                            if pid in prior:continue
                            prior.add(pid)
                            row=self._candidate(c,point,project,generation)
                            if row is None:continue
                            candidates[pid]=row
                            scores[pid]=scores.get(pid,0.0)+1.0/(60+position)
                item_count=len({row['item_uid'] for row in candidates.values()})
                if item_count>=payload.top_k or all(exhausted.values()):break
            grouped={}
            for pid,row in candidates.items():grouped.setdefault(row['item_uid'],[]).append((pid,scores[pid],row))
            for chunks in grouped.values():chunks.sort(key=lambda item:(-item[1],item[0]))
            ranked=sorted(grouped.items(),key=lambda item:(item[0] not in exact,-item[1][0][1],item[0]))[:payload.top_k]
            results=[self._restore(c,chunks[0][2],chunks,payload.response,set(allowed_projects)) for _,chunks in ranked]
            source_exhausted=all(exhausted.values())
            return {'total':len(results),'results':results,'exhausted':source_exhausted,
                    'backfill_limited':len(results)<payload.top_k and not source_exhausted,
                    'rounds':rounds,'unindexed_project_uids':[p for p in payload.project_uids if p not in pairs]}

    def item_detail(self,project_uid,item_uid,*,allowed_projects):
        self._authorize([project_uid],allowed_projects)
        with self.readers.snapshot([project_uid]) as (c,pairs):
            generation=pairs.get(project_uid)
            row=c.execute("""SELECT r.raw_payload,r.revision_uid,r.source_revision,m.scope_id FROM items i
                JOIN item_revisions r ON r.revision_uid=i.active_revision_uid AND r.item_uid=i.item_uid
                JOIN index_publications p ON p.item_uid=i.item_uid AND p.revision_uid=r.revision_uid AND p.generation_uid=?
                JOIN collection_memberships m ON m.project_uid=i.project_uid AND m.source_item_id=i.source_item_id
                WHERE i.item_uid=? AND i.project_uid=? AND i.deleted_state NOT IN ('deleted','unauthorized')
                AND m.state IN ('IN_SCOPE','MISSING')""",(generation,item_uid,project_uid)).fetchone()
            if row is None or not allows_scope(c,project_uid,row['scope_id']):raise SearchError('NOT_FOUND',404)
            blocks=[]
            for block in c.execute('SELECT b.* FROM content_blocks b WHERE b.revision_uid=? AND b.block_uid IN (SELECT c.block_uid FROM chunks c JOIN processing_membership m USING(chunk_uid) JOIN index_publications p ON p.result_uid=m.result_uid WHERE p.generation_uid=? AND p.item_uid=?) ORDER BY b.field_def_uid,b.block_order',(row['revision_uid'],generation,item_uid)):
                block=dict(block)
                if block['table_json'] is not None:block['table_json']=json.loads(block['table_json'])
                blocks.append(block)
            return {'project_uid':project_uid,'item_uid':item_uid,'revision_uid':row['revision_uid'],'source_revision':row['source_revision'],'item':self._raw(row),'content_blocks':blocks}
