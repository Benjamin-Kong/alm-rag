"""Local bootstrap and HTTP client. Secrets are entered without terminal echo."""
import getpass
import json
import os
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
    try:
        with httpx.Client(timeout=10,follow_redirects=False) as client:
            response=client.request(method,base+'/api/v1'+path,headers=headers,json=payload)
        if response.is_error:
            typer.echo('Request rejected (HTTP '+str(response.status_code)+').',err=True)
            raise typer.Exit(1)
        typer.echo(json.dumps(response.json()))
    except httpx.HTTPError:
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
    """Request a pipeline stage; M1 returns 409 until handlers are implemented."""
    from urllib.parse import quote
    request('POST','/projects/'+quote(project_uid,safe='')+'/jobs',{'stage':stage})


if __name__=='__main__':
    app()
