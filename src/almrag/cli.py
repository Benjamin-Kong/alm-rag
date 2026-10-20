"""Local bootstrap and HTTP client. Secrets are entered without terminal echo."""
import getpass
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote, urlsplit
import typer
import httpx

from almrag.config import Settings, endpoint
from almrag.security import Security, SecretVault

app=typer.Typer(no_args_is_help=True)


def database():
    from almrag.storage import Database
    settings=Settings.from_env()
    db=Database(settings.database_path)
    db.migrate()
    return db


@app.command()
def migrate():
    """Apply idempotent local migrations."""
    database()
    typer.echo('schema ready')


@app.command()
def bootstrap_admin(username:str=typer.Option('admin')):
    """Create the first administrator using a hidden password prompt."""
    password=getpass.getpass('New admin password (at least 16 characters): ')
    try:
        Security(database()).bootstrap(username,password)
    except ValueError:
        typer.echo('Administrator creation rejected.',err=True)
        raise typer.Exit(1)
    typer.echo('Administrator created. HTTPS is required for browser session cookies.')


@app.command()
def store_secret(ref:str):
    """Encrypt a secret using ALMRAG_MASTER_KEY; never echo its value."""
    settings=Settings.from_env()
    if not settings.master_key:
        typer.echo('ALMRAG_MASTER_KEY is required.',err=True)
        raise typer.Exit(1)
    try:
        SecretVault(database(),settings.master_key).put(ref,getpass.getpass('Secret: '))
    except ValueError:
        typer.echo('Secret storage rejected.',err=True)
        raise typer.Exit(1)
    typer.echo('Secret stored.')


def request(method,path,payload=None):
    base=endpoint(os.getenv('ALMRAG_API_URL','http://127.0.0.1:8000'))
    headers={}
    if os.getenv('ALMRAG_API_KEY'):
        headers['X-API-Key']=os.environ['ALMRAG_API_KEY']
    else:
        token=os.getenv('ALMRAG_SESSION_TOKEN')
        csrf=os.getenv('ALMRAG_CSRF_TOKEN','')
        session_file=Path(os.getenv('ALMRAG_SESSION_FILE','data/client-session.json'))
        if not token and session_file.exists():
            try:
                session=json.loads(session_file.read_text())
                if session['base_url']!=base:raise ValueError('session origin mismatch')
                token,csrf=session['token'],session['csrf']
            except (ValueError,OSError,KeyError,TypeError):
                typer.echo('Session unavailable or belongs to a different API URL.',err=True)
                raise typer.Exit(1)
        if token:
            if urlsplit(base).scheme!='https':
                typer.echo('HTTPS is required for administrator sessions.',err=True)
                raise typer.Exit(1)
            headers.update({'Cookie':'almrag_session='+token,'X-CSRF-Token':csrf,'Origin':base})
    try:
        with httpx.Client(timeout=180,follow_redirects=False,trust_env=False) as client:
            response=client.request(method,base+'/api/v1'+path,headers=headers,json=payload)
        if response.is_error:
            typer.echo('Request rejected (HTTP '+str(response.status_code)+').',err=True)
            raise typer.Exit(1)
        typer.echo(json.dumps(response.json()))
    except (httpx.HTTPError,ValueError):
        typer.echo('API unavailable.',err=True)
        raise typer.Exit(1)


@app.command()
def health():
    """Read public API liveness."""
    request('GET','/healthz')


@app.command()
def jobs():
    """List jobs within the supplied API key scope."""
    request('GET','/jobs')


@app.command()
def start_job(project_uid:str,stage:str):
    """Request a supported collection, processing, indexing or SYNC stage."""
    request('POST','/projects/'+quote(project_uid,safe='')+'/jobs',{'stage':stage})


def _payload(path):
    try:
        value=json.loads(Path(path).read_text())
        if not isinstance(value,dict):raise ValueError('object required')
        return value
    except (OSError,ValueError):
        typer.echo('Cannot read a JSON configuration object.',err=True)
        raise typer.Exit(1)


@app.command()
def login(username:str=typer.Option('admin')):
    """Log in over HTTPS and save a private, API-bound session file."""
    base=endpoint(os.getenv('ALMRAG_API_URL','https://localhost:8443'))
    if urlsplit(base).scheme!='https':
        typer.echo('HTTPS is required for administrator sessions.',err=True)
        raise typer.Exit(1)
    try:
        with httpx.Client(timeout=10,follow_redirects=False,trust_env=False) as client:
            response=client.post(base+'/api/v1/auth/login',headers={'Origin':base},json={'username':username,'password':getpass.getpass('Admin password: ')})
        if response.status_code!=204:raise ValueError('login rejected')
        session={'base_url':base,'token':response.cookies['almrag_session'],'csrf':response.cookies['almrag_csrf']}
        path=Path(os.getenv('ALMRAG_SESSION_FILE','data/client-session.json'))
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        temporary=None
        try:
            with NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as stream:
                temporary=Path(stream.name)
                os.chmod(temporary,0o600)
                json.dump(session,stream)
            temporary.replace(path)
        finally:
            if temporary:temporary.unlink(missing_ok=True)
    except (httpx.HTTPError,ValueError,KeyError,OSError):
        typer.echo('Login or private session storage failed.',err=True)
        raise typer.Exit(1)
    typer.echo('Administrator session saved.')


@app.command()
def register_source(config_file:str):
    """Register a profile JSON with auth_ref only; never inline credentials."""
    request('POST','/alm-instances',_payload(config_file))


@app.command()
def register_project(config_file:str):
    """Register a discovered project and initial source-specific scope."""
    request('POST','/projects',_payload(config_file))


@app.command()
def discover_projects(instance_uid:str):
    request('GET','/alm-instances/'+quote(instance_uid,safe='')+'/projects')


@app.command()
def discover_scopes(instance_uid:str,source_project_id:str):
    request('GET','/alm-instances/'+quote(instance_uid,safe='')+'/projects/'+quote(source_project_id,safe='')+'/scopes')


@app.command()
def discover_fields(instance_uid:str,source_project_id:str):
    request('GET','/alm-instances/'+quote(instance_uid,safe='')+'/projects/'+quote(source_project_id,safe='')+'/fields')


@app.command()
def configure_collection(project_uid:str,config_file:str):
    request('PUT','/projects/'+quote(project_uid,safe='')+'/collection-config',_payload(config_file))


@app.command()
def preflight(project_uid:str):
    request('POST','/projects/'+quote(project_uid,safe='')+'/preflight')


@app.command()
def collect(project_uid:str,config_revision:str|None=typer.Option(None)):
    request('POST','/projects/'+quote(project_uid,safe='')+'/jobs',{'stage':'COLLECT','config_revision':config_revision})


@app.command()
def configure_processing(project_uid:str,config_file:str):
    request('PUT','/projects/'+quote(project_uid,safe='')+'/processing-config',_payload(config_file))


@app.command()
def processing_preflight(project_uid:str):
    request('POST','/projects/'+quote(project_uid,safe='')+'/processing-preflight')


@app.command()
def process(project_uid:str,config_revision:str|None=typer.Option(None)):
    request('POST','/projects/'+quote(project_uid,safe='')+'/jobs',{'stage':'PROCESS','config_revision':config_revision})


@app.command()
def embed(project_uid:str,config_revision:str|None=typer.Option(None)):
    request('POST','/projects/'+quote(project_uid,safe='')+'/jobs',{'stage':'EMBED','config_revision':config_revision})


@app.command()
def search(query:str,project:list[str]=typer.Option(...,'--project'),top_k:int=typer.Option(10,min=1,max=100),full:bool=False,item_uid:list[str]|None=typer.Option(None,'--item-uid'),source_item_id:list[str]|None=typer.Option(None,'--source-item-id'),scope:list[str]|None=typer.Option(None,'--scope'),filters:str|None=typer.Option(None,'--filters')):
    payload={'query':query,'project_uids':project,'top_k':top_k,'response':{'include_full_item':full}}
    try:
        def unique_object(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('duplicate property')
                result[key]=value
            return result
        def invalid_constant(value):raise ValueError('nonfinite JSON')
        selected=json.loads(filters,object_pairs_hook=unique_object,parse_constant=invalid_constant) if filters is not None else {}
        if not isinstance(selected,dict):raise ValueError('object required')
        for key,value in [('item_uids',item_uid),('source_item_ids',source_item_id),('source_scope_ids',scope)]:
            if value:
                if key in selected:raise ValueError('conflicting predicate')
                selected[key]=value
        if filters is not None or selected:payload['filters']=selected
    except (TypeError,ValueError,RecursionError):
        typer.echo('Invalid search filters.',err=True)
        raise typer.Exit(1)
    request('POST','/search',payload)


@app.command()
def item(item_uid:str):
    request('GET','/items/'+quote(item_uid,safe=''))


@app.command()
def index(project_uid:str,config_revision:str|None=typer.Option(None)):
    request('POST','/projects/'+quote(project_uid,safe='')+'/jobs',{'stage':'INDEX','config_revision':config_revision})


@app.command()
def rebuild_index(project_uid:str,config_revision:str|None=typer.Option(None)):
    request('POST','/projects/'+quote(project_uid,safe='')+'/jobs',{'stage':'REBUILD_INDEX','config_revision':config_revision})


@app.command()
def index_preflight(project_uid:str,stage:str='INDEX'):
    request('POST','/projects/'+quote(project_uid,safe='')+'/index-preflight?stage='+quote(stage,safe=''))


@app.command()
def pipeline_preflight(project_uid:str):
    request('POST','/projects/'+quote(project_uid,safe='')+'/pipeline-preflight')


@app.command()
def sync(project_uid:str,config_revision:str|None=typer.Option(None)):
    request('POST','/projects/'+quote(project_uid,safe='')+'/jobs',{'stage':'SYNC','config_revision':config_revision})


@app.command()
def failed_items(job_id:str,limit:int=typer.Option(100,min=1,max=1000),offset:int=typer.Option(0,min=0)):
    request('GET','/jobs/'+quote(job_id,safe='')+'/failed-items?limit='+str(limit)+'&offset='+str(offset))


@app.command()
def retry_item(job_id:str,item_uid:str,from_stage:str='FAILED_STAGE',force_recollect:bool=False,expected_revision_uid:str|None=typer.Option(None)):
    request('POST','/jobs/'+quote(job_id,safe='')+'/failed-items/'+quote(item_uid,safe='')+'/retry',{'from_stage':from_stage,'force_recollect':force_recollect,'expected_revision_uid':expected_revision_uid})


@app.command()
def retry_failed_items(job_id:str,from_stage:str='FAILED_STAGE',force_recollect:bool=False,expected_revision_uid:str|None=typer.Option(None)):
    request('POST','/jobs/'+quote(job_id,safe='')+'/failed-items/retry',{'from_stage':from_stage,'force_recollect':force_recollect,'expected_revision_uid':expected_revision_uid})


@app.command()
def resume(job_id:str):
    request('POST','/jobs/'+quote(job_id,safe='')+'/resume')


if __name__=='__main__':
    app()
