"""Scoped administration views and local artifact operations; no ALM writes."""
import json
import re
from fastapi import Query,Request,Response
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from almrag.security import digest
from almrag.docs_publish import Summary,SummaryOutbox


class SummaryQueued(BaseModel):
    summary_uid:str
    state:Literal['PENDING']='PENDING'

class PrincipalInfo(BaseModel):
    admin_session:bool
    project_uids:list[str]
    permissions:list[str]

class ItemMetadata(BaseModel):
    item_uid:str
    source_item_id:str
    active_revision_uid:str|None=None
    latest_revision_uid:str|None=None
    deleted_state:str

class RevisionInfo(BaseModel):
    revision_uid:str
    source_revision:str
    hash:str
    item:dict

class ChunkInfo(BaseModel):
    chunk_uid:str
    revision_uid:str
    input_text:str
    input_tokens:int
    content_hash:str
    source_span_offsets:list[dict]
    row_ids:list[str]
    vector_status:str|None=None

class DiagnosticInfo(BaseModel):
    job_id:str
    project_uid:str
    alm_instance_uid:str
    item_uid:str|None=None
    source_item_id:str|None=None
    stage:str
    state:str
    attempt:int=1
    http_status:int|None=None
    error_code:str|None=None
    trace_id:str|None=None
    trace_generated:bool=False

class ArtifactInfo(BaseModel):
    artifact_ref:str
    project_uid:str|None=None
    kind:str
    sha256:str
    size:int
    state:str
    created_at:float

class StrictInput(BaseModel):
    model_config=ConfigDict(extra='forbid')

class ProjectImportRequest(StrictInput):
    artifact_ref:str=Field(min_length=1,max_length=100)
    import_mode:Literal['MERGE_ONLY']='MERGE_ONLY'
    expected_sha256:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')

class BackupSchedule(StrictInput):
    interval_seconds:int=Field(ge=60,le=31536000)
    retention:int=Field(ge=1,le=1000)

class RestorePreparation(BaseModel):
    manifest_hash:str
    confirmation_nonce:str
    expires_at:float
    state:str

class BackupRestoreRequest(StrictInput):
    manifest_hash:str=Field(pattern=r'^[0-9a-f]{64}$')
    confirmation_nonce:str=Field(min_length=16,max_length=200)

class RecoveryInfo(BaseModel):
    recovery_ref:str
    state:Literal['RAW_ONLY_REBUILD_REQUIRED']
    auth_state:Literal['REREGISTRATION_REQUIRED']


def register_admin_routes(app,db,settings,auth,connections,require,project_exists,ApiFailure,InstanceDetail,JobInfo):
    def getops():
        if app.state.operations is None:
            from almrag.operations import OperationsService
            app.state.operations=OperationsService(db,attachment_root=settings.attachment_directory)
        return app.state.operations

    def invoke(name,*args,**kwargs):
        try:return getattr(getops(),name)(*args,**kwargs)
        except Exception as exc:
            code=getattr(exc,'code',None)
            if isinstance(code,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',code):
                raise ApiFailure(getattr(exc,'status',409),code) from None
            raise

    def item_owner(request,uid):
        with db.connect() as c:row=c.execute('SELECT project_uid FROM items WHERE item_uid=?',(uid,)).fetchone()
        if row is None:raise ApiFailure(404,'NOT_FOUND')
        require(request,'project_read',row[0]);return row[0]

    def job_owner(request,uid):
        with db.connect() as c:row=c.execute('SELECT project_uid FROM jobs WHERE job_id=?',(uid,)).fetchone()
        if row is None:raise ApiFailure(404,'NOT_FOUND')
        require(request,'project_read',row[0]);return row[0]

    def artifact_owner(request,ref):
        info=invoke('get_artifact',ref)
        if info['project_uid'] is None:require(request,'system_admin',session_only=True)
        else:require(request,'project_read',info['project_uid'])
        return info

    def admin(request):
        principal=require(request,'system_admin',session_only=True)
        return digest('admin:'+principal['username'])

    def audit(request,action,project=None):
        p=request.state.principal
        auth.audit(action=action,outcome='ok',actor_ref=digest('admin:'+p['username'] if p['admin_session'] else 'key:'+p['key_id']),project_uid=project,trace_id=request.state.trace_id)

    extra={'x-required-scope':'authenticated','x-milestone':'M5'}
    @app.get('/api/v1/auth/me',response_model=PrincipalInfo,operation_id='getPrincipal',openapi_extra=extra)
    def me(request:Request):
        p=request.state.principal
        return dict(admin_session=p['admin_session'],project_uids=[] if p['admin_session'] else p['project_uids'],permissions=['system_admin','project_read','project_manage','search'] if p['admin_session'] else p['permissions'])

    @app.get('/api/v1/alm-instances',response_model=list[InstanceDetail],operation_id='listAlmInstances',openapi_extra={'x-required-scope':'system_admin','x-session-only':True,'x-milestone':'M5'})
    def instances(request:Request,limit:int=Query(100,ge=1,le=1000),offset:int=Query(0,ge=0)):
        require(request,'system_admin',session_only=True)
        with db.connect() as c:uids=[r[0] for r in c.execute('SELECT instance_uid FROM connection_profiles ORDER BY instance_uid LIMIT ? OFFSET ?',(limit,offset))]
        return [connections.detail(uid) for uid in uids]

    @app.get('/api/v1/projects/{project_uid}/items',response_model=list[ItemMetadata],operation_id='listProjectItems',openapi_extra={'x-required-scope':'project_read','x-milestone':'M5'})
    def items(project_uid:str,request:Request,limit:int=Query(100,ge=1,le=1000),offset:int=Query(0,ge=0)):
        require(request,'project_read',project_uid);project_exists(project_uid)
        with db.connect() as c:return [dict(r) for r in c.execute('SELECT i.item_uid,i.source_item_id,i.active_revision_uid,i.deleted_state,s.latest_revision_uid FROM items i LEFT JOIN item_collection_state s USING(item_uid) WHERE i.project_uid=? ORDER BY i.source_item_id LIMIT ? OFFSET ?',(project_uid,limit,offset))]

    @app.get('/api/v1/items/{item_uid}/revisions',response_model=list[RevisionInfo],operation_id='getItemRevisions',openapi_extra={'x-required-scope':'project_read','x-milestone':'M5'})
    def revisions(item_uid:str,request:Request,limit:int=Query(100,ge=1,le=1000),offset:int=Query(0,ge=0)):
        item_owner(request,item_uid)
        with db.connect() as c:return [dict(revision_uid=r['revision_uid'],source_revision=r['source_revision'],hash=r['hash'],item=json.loads(r['raw_payload'])) for r in c.execute('SELECT * FROM item_revisions WHERE item_uid=? ORDER BY captured_at DESC,revision_uid LIMIT ? OFFSET ?',(item_uid,limit,offset))]

    @app.get('/api/v1/items/{item_uid}/chunks',response_model=list[ChunkInfo],operation_id='getItemChunks',openapi_extra={'x-required-scope':'project_read','x-milestone':'M5'})
    def chunks(item_uid:str,request:Request,limit:int=Query(100,ge=1,le=1000),offset:int=Query(0,ge=0)):
        item_owner(request,item_uid)
        with db.connect() as c:
            rows=c.execute("SELECT c.*, (SELECT p.vector_status FROM index_points p WHERE p.chunk_uid=c.chunk_uid ORDER BY CASE p.vector_status WHEN 'READY' THEN 0 ELSE 1 END LIMIT 1) AS vector_status FROM chunks c JOIN item_revisions r USING(revision_uid) WHERE r.item_uid=? ORDER BY c.revision_uid,c.chunk_uid LIMIT ? OFFSET ?",(item_uid,limit,offset)).fetchall()
        return [{**dict(r),'source_span_offsets':json.loads(r['source_span_offsets']),'row_ids':json.loads(r['row_ids'])} for r in rows]

    @app.get('/api/v1/jobs/{job_id}/diagnostics',response_model=list[DiagnosticInfo],operation_id='getJobDiagnostics',openapi_extra={'x-required-scope':'project_read','x-milestone':'M5'})
    def diagnostics(job_id:str,request:Request,limit:int=Query(100,ge=1,le=1000),offset:int=Query(0,ge=0)):
        project=job_owner(request,job_id)
        with db.connect() as c:
            instance=c.execute('SELECT instance_uid FROM projects WHERE project_uid=?',(project,)).fetchone()[0]
            query="""SELECT * FROM (SELECT o.item_uid,o.source_item_id,'COLLECT' AS stage,o.state,o.error_code,NULL AS trace_id,COALESCE(f.attempts,1) AS attempt FROM collection_outcomes o LEFT JOIN collection_failures f ON f.job_id=o.job_id AND f.source_item_id=o.source_item_id WHERE o.job_id=?
                UNION ALL SELECT o.item_uid,NULL,j.stage,o.state,o.error_code,f.trace_id,COALESCE(f.attempts,1) FROM processing_outcomes o JOIN jobs j ON j.job_id=o.job_id LEFT JOIN failed_items f ON f.job_id=o.job_id AND f.item_uid=o.item_uid AND f.failed_stage=j.stage WHERE o.job_id=?
                UNION ALL SELECT o.item_uid,NULL,'INDEX',o.state,o.error_code,f.trace_id,COALESCE(f.attempts,1) FROM index_outcomes o LEFT JOIN failed_items f ON f.job_id=o.job_id AND f.item_uid=o.item_uid AND f.failed_stage='INDEX' WHERE o.job_id=?
                UNION ALL SELECT o.item_uid,NULL,o.stage,o.state,o.error_code,f.trace_id,COALESCE(f.attempts,1) FROM pipeline_steps o LEFT JOIN failed_items f ON f.job_id=o.job_id AND f.item_uid=o.item_uid AND f.failed_stage=o.stage WHERE o.job_id=?
                ) ORDER BY item_uid,source_item_id,stage LIMIT ? OFFSET ?"""
            rows=c.execute(query,(job_id,job_id,job_id,job_id,limit,offset)).fetchall()
            from almrag.storage import canonical_uid
            result=[]
            for row in rows:
                value=dict(row);code=value['error_code']
                if code and not re.fullmatch('[A-Z][A-Z0-9_]{0,63}',code):value['error_code']='UNKNOWN_ERROR';code=None
                value['http_status']=int(code[5:]) if code and re.fullmatch(r'HTTP_[1-5][0-9]{2}',code) else None
                if not value['trace_id']:
                    value['trace_id']=canonical_uid('diagnostic',job_id,value['item_uid'] or value['source_item_id'],value['stage']);value['trace_generated']=True
                result.append(dict(value,job_id=job_id,project_uid=project,alm_instance_uid=instance))
            return result

    @app.post('/api/v1/projects/{project_uid}/export',status_code=202,response_model=JobInfo,operation_id='exportProject',openapi_extra={'x-required-scope':'project_manage','x-milestone':'M5'})
    def export(project_uid:str,request:Request):
        require(request,'project_manage',project_uid);project_exists(project_uid)
        result=invoke('enqueue_export',project_uid);audit(request,'artifact_export',project_uid);return result

    @app.post('/api/v1/projects/{project_uid}/import',status_code=202,response_model=JobInfo,operation_id='importProject',openapi_extra={'x-required-scope':'project_manage','x-milestone':'M5'})
    def import_project(project_uid:str,payload:ProjectImportRequest,request:Request):
        require(request,'project_manage',project_uid);project_exists(project_uid)
        result=invoke('enqueue_import',project_uid,**payload.model_dump());audit(request,'artifact_import',project_uid);return result

    @app.get('/api/v1/projects/{project_uid}/artifacts',response_model=list[ArtifactInfo],operation_id='listProjectArtifacts',openapi_extra={'x-required-scope':'project_read','x-milestone':'M5'})
    def artifacts(project_uid:str,request:Request):
        require(request,'project_read',project_uid);project_exists(project_uid);return invoke('list_artifacts',project_uid)

    @app.post('/api/v1/projects/{project_uid}/artifacts/stage',status_code=201,response_model=ArtifactInfo,operation_id='stageProjectArtifact',openapi_extra={'x-required-scope':'project_manage','x-milestone':'M5','requestBody':{'required':True,'content':{'application/zip':{'schema':{'type':'string','format':'binary'}}}}})
    async def stage(project_uid:str,request:Request):
        require(request,'project_manage',project_uid);project_exists(project_uid)
        if request.headers.get('content-type','').split(';')[0]!='application/zip':raise ApiFailure(415,'ZIP_REQUIRED')
        data=bytearray()
        async for part in request.stream():
            if len(data)+len(part)>64*1024*1024:raise ApiFailure(413,'ARTIFACT_TOO_LARGE')
            data.extend(part)
        return invoke('register_package',project_uid,bytes(data))

    @app.get('/api/v1/artifacts/{artifact_ref}/download',operation_id='downloadArtifact',response_class=Response,openapi_extra={'x-required-scope':'project_read','x-milestone':'M5','responses':{'200':{'description':'Authorized local artifact bytes','content':{'application/zip':{'schema':{'type':'string','format':'binary'}}}}}})
    def download(artifact_ref:str,request:Request):
        info=artifact_owner(request,artifact_ref)
        data=invoke('read_artifact',artifact_ref)
        return Response(data,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="'+info['artifact_ref']+'.zip"'})

    @app.post('/api/v1/backups',status_code=201,response_model=ArtifactInfo,operation_id='createBackup',openapi_extra={'x-required-scope':'system_admin','x-session-only':True,'x-milestone':'M5'})
    def backup(request:Request):
        admin(request);result=invoke('create_backup');audit(request,'backup_create');return result

    @app.get('/api/v1/backups',response_model=list[ArtifactInfo],operation_id='listBackups',openapi_extra={'x-required-scope':'system_admin','x-session-only':True,'x-milestone':'M5'})
    def backups(request:Request):
        admin(request);return invoke('list_backups')

    @app.put('/api/v1/backups/schedule',response_model=BackupSchedule,operation_id='configureBackupSchedule',openapi_extra={'x-required-scope':'system_admin','x-session-only':True,'x-milestone':'M5'})
    def schedule(payload:BackupSchedule,request:Request):
        admin(request);return invoke('configure_backup_schedule',**payload.model_dump())

    @app.post('/api/v1/backups/{backup_id}/prepare-restore',response_model=RestorePreparation,operation_id='prepareRestore',openapi_extra={'x-required-scope':'system_admin','x-session-only':True,'x-milestone':'M5'})
    def prepare_restore(backup_id:str,request:Request):
        return invoke('prepare_restore',backup_id,admin(request))

    @app.post('/api/v1/backups/{backup_id}/restore',response_model=RecoveryInfo,operation_id='restoreBackup',openapi_extra={'x-required-scope':'system_admin','x-session-only':True,'x-milestone':'M5'})
    def restore(backup_id:str,payload:BackupRestoreRequest,request:Request):
        result=invoke('restore',backup_id,actor=admin(request),**payload.model_dump());audit(request,'backup_restore');return result

    @app.post('/api/v1/docs/summaries',status_code=202,response_model=SummaryQueued,operation_id='enqueueDocSummary',openapi_extra={'x-required-scope':'system_admin','x-session-only':True,'x-milestone':'M5'})
    def summary(payload:Summary,request:Request):
        admin(request)
        return {'summary_uid':SummaryOutbox(db).enqueue(payload),'state':'PENDING'}
