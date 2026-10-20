"""Authenticated source administration and collection; later stages fail closed."""
import json
import secrets
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from almrag.config import Settings
from almrag.security import Security, digest
from almrag.alm_http import AlmError, HttpPolicy
from almrag.collection import CollectionError, CollectionService
from almrag.connection import Connections, SourceProfileCreate
from almrag.connectors import ConnectorError


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Input):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class KeyCreate(Input):
    name: str = Field(min_length=1, max_length=128)
    project_uids: list[str] = Field(min_length=1, max_length=1000)
    permissions: list[Literal['search','project_read','project_manage','system_admin']] = Field(min_length=1, max_length=4)


class KeyCreated(BaseModel):
    key_id: str
    key: str


class Stage(Input):
    stage: Literal['SYNC','COLLECT','PROCESS','EMBED','INDEX','REBUILD_INDEX']
    force: bool = False
    config_revision: str | None = None


class Health(BaseModel):
    status: Literal['ok'] = 'ok'


class ProjectInfo(BaseModel):
    project_uid: str
    alm_instance_uid: str
    source_project_id: str
    name: str


class JobInfo(BaseModel):
    job_id: str
    project_uid: str
    stage: str
    state: Literal['QUEUED','RUNNING','SUCCEEDED','COMPLETED_WITH_ERRORS','RETRY_WAIT','PAUSED','BLOCKED','FAILED','CANCELLED']
    last_error_code: str | None = None


class ApiError(BaseModel):
    code: str
    message: str
    trace_id: str


class CollectionConfig(Input):
    selection_mode: Literal['ALL','SELECTED'] = 'ALL'
    scope_kind: Literal['TRACKER','WORK_ITEM_TYPE']
    source_scope_ids: list[str] = Field(default_factory=list,max_length=10000)
    embedding_fields: list[str] = Field(default_factory=lambda:['title','description'],min_length=1,max_length=1000)


class ProjectCreate(CollectionConfig):
    alm_instance_uid: str
    source_project_id: str = Field(min_length=1,max_length=200)
    name: str = Field(min_length=1,max_length=200)


class InstanceInfo(BaseModel):
    instance_uid: str
    source_type: Literal['codebeamer','polarion']
    display_name: str
    base_url: str
    api_profile: str
    auth_configured: bool


class SourceProject(BaseModel):
    id: str
    name: str
    url: str


class SourceScope(BaseModel):
    id: str
    name: str
    kind: Literal['TRACKER','WORK_ITEM_TYPE']


class PreflightInfo(BaseModel):
    status: Literal['READY','BLOCKED']
    collect_ready: bool
    sync_ready: bool
    scope_kind: str | None
    source_scope_ids: list[str]
    readable_fields: list[dict]
    normalized_fields: list[str] = Field(default_factory=list)
    estimated_items: int | None
    estimated_requests: int | None
    request_estimate_kind: Literal['UNKNOWN'] = 'UNKNOWN'
    request_count_lower_bound: int | None = None
    config_revision: str | None
    diagnostics: list[str]


class JobEvent(BaseModel):
    event_id: int
    job_id: str
    occurred_at: float
    state: str
    error_code: str | None = None


class ApiFailure(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def error(request, status, code):
    return JSONResponse(status_code=status, content={'code':code,'message':code.lower().replace('_',' '), 'trace_id':request.state.trace_id}, headers={'Cache-Control':'no-store'})


def create_app(settings=None, db=None, *, connections=None, collection=None):
    settings = settings or Settings.from_env()
    if db is None:
        from almrag.storage import Database
        db = Database(settings.database_path)
        db.migrate()
    auth = Security(db, settings.session_seconds)
    connections=connections or Connections(db,settings)
    collection=collection or CollectionService(db,connections.connector,settings.attachment_directory)
    app = FastAPI(title='ALM RAG M2', version='0.2.0', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.security, app.state.db = auth, db
    app.state.connections,app.state.collection=connections,collection

    @app.exception_handler(AlmError)
    @app.exception_handler(CollectionError)
    @app.exception_handler(ConnectorError)
    async def source_failure(request,exc):
        code=exc.code
        if code in {'INSTANCE_NOT_FOUND','PROJECT_NOT_CONFIGURED'}:status=404
        elif code in {'STALE_PREFLIGHT'}:status=409
        elif code in {'INVALID_SCOPE','INVALID_SCOPE_KIND','EMPTY_SCOPE','INVALID_FIELDS','PROJECT_NOT_DISCOVERED','SCOPE_NOT_DISCOVERED'}:status=422
        else:status=503
        return error(request,status,code)

    @app.exception_handler(ApiFailure)
    async def failure(request, exc):
        if exc.status in {403,404}:
            auth.audit(action='request',outcome='denied',error_code=exc.code,trace_id=request.state.trace_id)
        return error(request, exc.status, exc.code)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return error(request, 422, 'INVALID_REQUEST')

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        request.state.trace_id = str(uuid4())
        request.state.principal = None
        try:
            public = request.url.path in {'/api/v1/healthz','/api/v1/auth/login'}
            if request.url.path == '/api/v1/auth/login' and request.headers.get('origin') != settings.allowed_origin:
                auth.audit(action='request',outcome='denied',error_code='FORBIDDEN',trace_id=request.state.trace_id)
                return error(request,403,'FORBIDDEN')
            if not public:
                raw_key = request.headers.get('x-api-key')
                token = request.cookies.get('almrag_session','')
                principal = auth.api_key(raw_key) if raw_key else auth.session(token)
                if principal is None:
                    auth.audit(action='request',outcome='denied',error_code='INVALID_AUTH',trace_id=request.state.trace_id)
                    return error(request,401,'INVALID_AUTH')
                principal['admin_session'] = not bool(raw_key)
                if not raw_key and request.method not in {'GET','HEAD','OPTIONS'}:
                    csrf = request.headers.get('x-csrf-token','')
                    if request.headers.get('origin') != settings.allowed_origin or not secrets.compare_digest(digest(csrf),principal['csrf_hash']):
                        auth.audit(action='request',outcome='denied',error_code='FORBIDDEN',trace_id=request.state.trace_id)
                        return error(request,403,'FORBIDDEN')
                request.state.principal = principal
            result = await call_next(request)
        except sqlite3.Error:
            return error(request,503,'DATABASE_UNAVAILABLE')
        result.headers['Cache-Control'] = 'no-store'
        result.headers['X-Content-Type-Options'] = 'nosniff'
        result.headers['X-Request-ID'] = request.state.trace_id
        return result

    def require(request, permission, project=None, session_only=False):
        p=request.state.principal
        if not p:
            raise ApiFailure(401,'INVALID_AUTH')
        if p['admin_session']:
            return p
        if session_only or permission not in p['permissions']:
            raise ApiFailure(403,'FORBIDDEN')
        if project is not None and project not in p['project_uids']:
            raise ApiFailure(404,'NOT_FOUND')
        return p

    def project_exists(project):
        with db.connect() as c:
            if not c.execute('SELECT 1 FROM projects WHERE project_uid=?',(project,)).fetchone():
                raise ApiFailure(404,'NOT_FOUND')

    @app.post('/api/v1/alm-instances',status_code=201,response_model=InstanceInfo,operation_id='registerAlmInstance',openapi_extra={'x-required-scope':'system_admin','x-session-only':True})
    def register_instance(payload:SourceProfileCreate,request:Request):
        require(request,'system_admin',session_only=True)
        return connections.register(payload)

    @app.post('/api/v1/alm-instances/{instance_uid}/probe',response_model=dict,operation_id='probeAlmInstance',openapi_extra={'x-required-scope':'system_admin','x-session-only':True})
    def probe_instance(instance_uid:str,request:Request):
        require(request,'system_admin',session_only=True)
        return connections.connector(instance_uid).probe()

    @app.get('/api/v1/alm-instances/{instance_uid}/projects',response_model=list[SourceProject],operation_id='discoverAlmProjects',openapi_extra={'x-required-scope':'system_admin','x-session-only':True})
    def discover_projects(instance_uid:str,request:Request):
        require(request,'system_admin',session_only=True)
        return connections.connector(instance_uid).list_projects()

    @app.get('/api/v1/alm-instances/{instance_uid}/projects/{source_project_id}/scopes',response_model=list[SourceScope],operation_id='discoverCollectionScopes',openapi_extra={'x-required-scope':'system_admin','x-session-only':True})
    def discover_scopes(instance_uid:str,source_project_id:str,request:Request):
        require(request,'system_admin',session_only=True)
        return connections.connector(instance_uid).list_scopes(source_project_id)

    @app.get('/api/v1/alm-instances/{instance_uid}/projects/{source_project_id}/fields',response_model=list[dict],operation_id='discoverCollectionFields',openapi_extra={'x-required-scope':'system_admin','x-session-only':True})
    def discover_fields(instance_uid:str,source_project_id:str,request:Request):
        require(request,'system_admin',session_only=True)
        return connections.connector(instance_uid).list_fields(source_project_id)

    @app.put('/api/v1/alm-instances/{instance_uid}/rate-policy',response_model=HttpPolicy,operation_id='setServerRateLimit',openapi_extra={'x-required-scope':'system_admin','x-session-only':True})
    def rate_policy(instance_uid:str,payload:HttpPolicy,request:Request):
        require(request,'system_admin',session_only=True)
        connections.set_policy(instance_uid,payload)
        return payload

    @app.post('/api/v1/projects',status_code=201,response_model=ProjectInfo,operation_id='registerProject',openapi_extra={'x-required-scope':'system_admin','x-session-only':True})
    def register_project(payload:ProjectCreate,request:Request):
        require(request,'system_admin',session_only=True)
        uid=collection.configure_project(payload.alm_instance_uid,payload.source_project_id,payload.name,payload.selection_mode,payload.scope_kind,payload.source_scope_ids,payload.embedding_fields)
        return ProjectInfo(project_uid=uid,alm_instance_uid=payload.alm_instance_uid,source_project_id=payload.source_project_id,name=payload.name)

    @app.put('/api/v1/projects/{project_uid}/collection-config',response_model=ProjectInfo,operation_id='configureCollectionScope',openapi_extra={'x-required-scope':'project_manage'})
    def collection_config(project_uid:str,payload:CollectionConfig,request:Request):
        require(request,'project_manage',project_uid)
        project_exists(project_uid)
        with db.connect() as c:row=c.execute('SELECT * FROM projects WHERE project_uid=?',(project_uid,)).fetchone()
        collection.configure_project(row['instance_uid'],row['source_project_id'],row['name'],payload.selection_mode,payload.scope_kind,payload.source_scope_ids,payload.embedding_fields)
        return ProjectInfo(project_uid=project_uid,alm_instance_uid=row['instance_uid'],source_project_id=row['source_project_id'],name=row['name'])

    @app.post('/api/v1/projects/{project_uid}/preflight',response_model=PreflightInfo,operation_id='preflightProject',openapi_extra={'x-required-scope':'project_manage'})
    def preflight_project(project_uid:str,request:Request):
        require(request,'project_manage',project_uid)
        project_exists(project_uid)
        return collection.preflight(project_uid)

    @app.get('/api/v1/healthz',response_model=Health,operation_id='healthz',openapi_extra={'x-required-scope':'public'})
    def health():
        return Health()

    @app.get('/api/v1/readyz',response_model=Health,operation_id='readyz',openapi_extra={'x-required-scope':'system_admin'})
    def ready(request: Request):
        require(request,'system_admin')
        with db.connect() as c:
            c.execute('SELECT 1 FROM projects LIMIT 1').fetchone()
            c.execute('SELECT 1 FROM jobs LIMIT 1').fetchone()
        return Health()

    @app.post('/api/v1/auth/login',status_code=204,operation_id='adminLogin',openapi_extra={'x-required-scope':'public'})
    def login(payload: Login, request: Request):
        found=auth.login(payload.username,payload.password,trace_id=request.state.trace_id)
        if not found:
            raise ApiFailure(401,'INVALID_AUTH')
        token,csrf=found
        response=Response(status_code=204)
        response.set_cookie('almrag_session',token,max_age=settings.session_seconds,secure=True,httponly=True,samesite='strict',path='/api/v1')
        response.set_cookie('almrag_csrf',csrf,max_age=settings.session_seconds,secure=True,httponly=False,samesite='strict',path='/')
        return response

    @app.post('/api/v1/auth/logout',status_code=204,operation_id='adminLogout',openapi_extra={'x-required-scope':'authenticated'})
    def logout(request: Request):
        require(request,'system_admin',session_only=True)
        auth.logout(request.cookies.get('almrag_session',''),trace_id=request.state.trace_id)
        response=Response(status_code=204)
        response.delete_cookie('almrag_session',path='/api/v1',secure=True,httponly=True,samesite='strict')
        response.delete_cookie('almrag_csrf',path='/',secure=True,samesite='strict')
        return response

    @app.post('/api/v1/api-keys',status_code=201,response_model=KeyCreated,operation_id='createApiKey',openapi_extra={'x-required-scope':'system_admin'})
    def create_key(payload: KeyCreate,request: Request):
        p=require(request,'system_admin')
        if not p['admin_session'] and (not set(payload.project_uids)<=set(p['project_uids']) or not set(payload.permissions)<=set(p['permissions'])):
            raise ApiFailure(403,'FORBIDDEN')
        for uid in payload.project_uids:
            project_exists(uid)
        actor='admin:'+p['username'] if p['admin_session'] else 'api_key:'+p['key_id']
        key_id,key=auth.create_key(payload.name,payload.project_uids,payload.permissions,actor=actor,trace_id=request.state.trace_id)
        return KeyCreated(key_id=key_id,key=key)

    @app.delete('/api/v1/api-keys/{key_id}',status_code=204,operation_id='revokeApiKey',openapi_extra={'x-required-scope':'system_admin'})
    def revoke(key_id:str,request:Request):
        p=require(request,'system_admin')
        if not p['admin_session']:
            with db.connect() as c:
                row=c.execute('SELECT project_uids,permissions FROM api_keys WHERE key_id=?',(key_id,)).fetchone()
            if not row or not set(json.loads(row['project_uids']))<=set(p['project_uids']) or not set(json.loads(row['permissions']))<=set(p['permissions']):
                raise ApiFailure(404,'NOT_FOUND')
        actor='admin:'+p['username'] if p['admin_session'] else 'api_key:'+p['key_id']
        auth.revoke_key(key_id,actor=actor,trace_id=request.state.trace_id)
        return Response(status_code=204)

    @app.get('/api/v1/projects',response_model=list[ProjectInfo],operation_id='listProjects',openapi_extra={'x-required-scope':'project_read'})
    def projects(request:Request,limit:int=100,offset:int=0):
        p=require(request,'project_read')
        if not 1<=limit<=1000 or offset<0:
            raise ApiFailure(422,'INVALID_REQUEST')
        with db.connect() as c:
            if p['admin_session']:
                rows=c.execute('SELECT * FROM projects ORDER BY project_uid LIMIT ? OFFSET ?',(limit,offset)).fetchall()
            else:
                marks=','.join('?' for _ in p['project_uids'])
                rows=c.execute(f'SELECT * FROM projects WHERE project_uid IN ({marks}) ORDER BY project_uid LIMIT ? OFFSET ?',(*p['project_uids'],limit,offset)).fetchall()
        return [ProjectInfo(project_uid=r['project_uid'],alm_instance_uid=r['instance_uid'],source_project_id=r['source_project_id'],name=r['name']) for r in rows]

    @app.get('/api/v1/jobs',response_model=list[JobInfo],operation_id='listJobs',openapi_extra={'x-required-scope':'project_read'})
    def jobs(request:Request,limit:int=100,offset:int=0):
        p=require(request,'project_read')
        if not 1<=limit<=1000 or offset<0:
            raise ApiFailure(422,'INVALID_REQUEST')
        with db.connect() as c:
            if p['admin_session']:
                rows=c.execute('SELECT * FROM jobs ORDER BY job_id LIMIT ? OFFSET ?',(limit,offset)).fetchall()
            else:
                marks=','.join('?' for _ in p['project_uids'])
                rows=c.execute(f'SELECT * FROM jobs WHERE project_uid IN ({marks}) ORDER BY job_id LIMIT ? OFFSET ?',(*p['project_uids'],limit,offset)).fetchall()
        return [JobInfo(**dict(r)) for r in rows]

    @app.get('/api/v1/jobs/{job_id}',response_model=JobInfo,operation_id='getJob',openapi_extra={'x-required-scope':'project_read'})
    def job(job_id:str,request:Request):
        require(request,'project_read')
        with db.connect() as c:
            row=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone()
        if not row:
            raise ApiFailure(404,'NOT_FOUND')
        require(request,'project_read',row['project_uid'])
        return JobInfo(**dict(row))

    @app.post('/api/v1/projects/{project_uid}/jobs',status_code=202,response_model=JobInfo,operation_id='startProjectStageJob',openapi_extra={'x-required-scope':'project_manage'})
    def stage(project_uid:str,payload:Stage,request:Request):
        require(request,'project_manage',project_uid)
        project_exists(project_uid)
        if payload.stage!='COLLECT':raise ApiFailure(409,'STAGE_UNAVAILABLE')
        return collection.enqueue(project_uid,payload.config_revision)

    @app.get('/api/v1/jobs/{job_id}/events',response_model=list[JobEvent],operation_id='listJobEvents',openapi_extra={'x-required-scope':'project_read'})
    def job_events(job_id:str,request:Request,limit:int=100,offset:int=0):
        job(job_id,request)
        if not 1<=limit<=1000 or offset<0:
            raise ApiFailure(422,'INVALID_REQUEST')
        with db.connect() as c:
            rows=c.execute('SELECT * FROM job_events WHERE job_id=? ORDER BY event_id LIMIT ? OFFSET ?',(job_id,limit,offset)).fetchall()
        return [JobEvent(**dict(row)) for row in rows]

    @app.post('/api/v1/projects/{project_uid}/sync',status_code=202,operation_id='startSync',openapi_extra={'x-required-scope':'project_manage'})
    def sync(project_uid:str,request:Request):
        return stage(project_uid,Stage(stage='SYNC'),request)

    @app.get('/api/v1/audit-events',response_model=list[dict],operation_id='listAuditEvents',openapi_extra={'x-required-scope':'system_admin'})
    def audit(request:Request,limit:int=100):
        require(request,'system_admin',session_only=True)
        if not 1<=limit<=1000:
            raise ApiFailure(422,'INVALID_REQUEST')
        with db.connect() as c:
            rows=c.execute('SELECT event FROM security_audit ORDER BY audit_id DESC LIMIT ?',(limit,)).fetchall()
        return [json.loads(r['event']) for r in rows]

    original_openapi=app.openapi
    def contract():
        schema=original_openapi()
        schema['components']['securitySchemes']={
            'ApiKeyAuth':{'type':'apiKey','in':'header','name':'X-API-Key'},
            'AdminSession':{'type':'apiKey','in':'cookie','name':'almrag_session','description':'Secure HttpOnly SameSite=strict; unsafe methods require Origin and X-CSRF-Token.'},
        }
        schema['components']['schemas']['ApiError']=ApiError.model_json_schema()
        for path,methods in schema['paths'].items():
            for method,op in methods.items():
                if method not in {'get','post','put','delete'}:
                    continue
                public=op['x-required-scope']=='public'
                op['security']=[] if public else [{'ApiKeyAuth':[]},{'AdminSession':[]}]
                if op.get('x-session-only') or path in {'/api/v1/audit-events','/api/v1/auth/logout'}:
                    op['security']=[{'AdminSession':[]}]
                op['x-implementation-status']='M1_IMPLEMENTED'
                if op.get('x-session-only') or 'collection-config' in path or 'preflight' in path:
                    op['x-implementation-status']='M2_IMPLEMENTED'
                codes=[422,503] + ([] if public else [401,403,404])
                if path.endswith('/auth/login'):
                    codes += [401,403]
                if method=='post' and (path.endswith('/jobs') or path.endswith('/sync')):
                    codes += [409]
                    if path.endswith('/sync'):
                        op['responses'].pop('202',None)
                        op['x-implementation-status']='M2_FAIL_CLOSED_SYNC_GUARD'
                    else:op['x-implementation-status']='M2_COLLECT_ONLY'
                for code in codes:
                    op['responses'][str(code)]={'description':'Sanitized error','content':{'application/json':{'schema':{'$ref':'#/components/schemas/ApiError'}}}}
        return schema
    app.openapi=contract
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_app(),host='0.0.0.0',port=8000,access_log=False)
