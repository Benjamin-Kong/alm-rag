"""Project-authorized bounded quality datasets, durable jobs and report views."""
import json
import re
from typing import Literal
from fastapi import Request
from pydantic import BaseModel,ConfigDict,Field,model_validator

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class GoldenCase(Strict):
    query:str=Field(min_length=1,max_length=65536)
    relevant_item_uids:list[str]=Field(min_length=1,max_length=1000)
    @model_validator(mode='after')
    def valid(self):
        if not self.query.strip() or any(not x.strip() or len(x)>256 for x in self.relevant_item_uids) or len(set(self.relevant_item_uids))!=len(self.relevant_item_uids):
            raise ValueError('nonblank unique Item IDs required')
        return self

class GoldenDataset(Strict):
    cases:list[GoldenCase]=Field(min_length=1,max_length=1000)
    @model_validator(mode='after')
    def bounded(self):
        if len(json.dumps(self.model_dump(),ensure_ascii=False).encode())>2*1024*1024:raise ValueError('dataset too large')
        return self

class DatasetInfo(Strict):
    dataset_ref:str
    project_uid:str
    case_count:int
    sha256:str

class EvaluationRequest(Strict):
    project_uids:list[str]=Field(min_length=1,max_length=1)
    dataset_ref:str=Field(min_length=1,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    methods:list[Literal['dense','keyword','hybrid']]=Field(default_factory=lambda:['dense','keyword','hybrid'],min_length=1,max_length=3)
    top_k:int=Field(default=10,ge=1,le=100,strict=True)
    @model_validator(mode='after')
    def unique(self):
        if len(self.methods)!=len(set(self.methods)):raise ValueError('duplicate methods')
        return self

class QualityReport(Strict):
    job_id:str
    project_uid:str
    stage:str
    status:str
    report:dict


def register_quality_routes(app,db,settings,require,project_exists,ApiFailure,JobInfo):
    def service():
        if app.state.quality is None:
            from almrag.quality import QualityService
            app.state.quality=QualityService(db,app.state.search,app.state.search.vector_store if settings.live_vector_enabled else None,attachment_root=settings.attachment_directory)
        return app.state.quality

    def invoke(method,*args,**kwargs):
        try:return getattr(service(),method)(*args,**kwargs)
        except Exception as exc:
            code=getattr(exc,'code',None);status=getattr(exc,'status',None)
            if isinstance(code,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',code) and status in (400,403,404,409,422,503):
                raise ApiFailure(status,code) from None
            raise ApiFailure(503,'QUALITY_UNAVAILABLE') from None

    def manage(request,p):
        require(request,'project_manage',p);project_exists(p)

    extra={'x-required-scope':'project_manage','x-milestone':'M6','x-implementation-status':'M6_IMPLEMENTED'}
    @app.post('/api/v1/projects/{project_uid}/evaluation-datasets',status_code=201,response_model=DatasetInfo,operation_id='stageEvaluationDataset',openapi_extra=extra)
    def stage_dataset(project_uid:str,payload:GoldenDataset,request:Request):
        manage(request,project_uid)
        return invoke('stage_dataset',project_uid,payload.model_dump())

    @app.post('/api/v1/projects/{project_uid}/integrity',status_code=202,response_model=JobInfo,operation_id='startIntegrityReport',openapi_extra=extra)
    def integrity(project_uid:str,request:Request):
        manage(request,project_uid)
        return invoke('enqueue_integrity',project_uid)

    @app.post('/api/v1/projects/{project_uid}/evaluations',status_code=202,response_model=JobInfo,operation_id='startRetrievalEvaluation',openapi_extra=extra)
    def evaluate(project_uid:str,payload:EvaluationRequest,request:Request):
        manage(request,project_uid)
        if payload.project_uids!=[project_uid]:raise ApiFailure(422,'EVALUATION_PROJECT_MISMATCH')
        return invoke('enqueue_evaluation',project_uid,payload.dataset_ref,methods=payload.methods,top_k=payload.top_k)

    @app.get('/api/v1/jobs/{job_id}/quality-report',response_model=QualityReport,operation_id='getQualityReport',openapi_extra={'x-required-scope':'project_read','x-milestone':'M6','x-implementation-status':'M6_IMPLEMENTED'})
    def quality_report(job_id:str,request:Request):
        with db.connect() as c:job=c.execute('SELECT project_uid,stage FROM jobs WHERE job_id=?',(job_id,)).fetchone()
        if job is None:raise ApiFailure(404,'NOT_FOUND')
        require(request,'project_read',job['project_uid'])
        report=invoke('report',job_id)
        if report.get('project_uid')!=job['project_uid'] or report.get('job_id')!=job_id or report.get('stage')!=job['stage']:
            raise ApiFailure(503,'QUALITY_REPORT_INTEGRITY')
        return report
