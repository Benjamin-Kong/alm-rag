"""SRS-045/046/047: discovery/selection usable without the M5 wizard."""
import json
import httpx
from typer.testing import CliRunner
from almrag import cli

runner=CliRunner()

def test_cli_collection_commands_and_quoted_ids(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(cli,'request',lambda method,path,payload=None:calls.append((method,path,payload)))
    profile=tmp_path/'profile.json';profile.write_text(json.dumps({'source_type':'codebeamer','auth_ref':'env:FIXTURE'}))
    config=tmp_path/'config.json';config.write_text(json.dumps({'scope_kind':'TRACKER','selection_mode':'SELECTED','source_scope_ids':['31']}))
    commands=[(['register-source',str(profile)],('POST','/alm-instances',json.loads(profile.read_text()))),
              (['register-project',str(config)],('POST','/projects',json.loads(config.read_text()))),
              (['discover-projects','source/id'],('GET','/alm-instances/source%2Fid/projects',None)),
              (['discover-scopes','source','project/id'],('GET','/alm-instances/source/projects/project%2Fid/scopes',None)),
              (['discover-fields','source','project'],('GET','/alm-instances/source/projects/project/fields',None)),
              (['configure-collection','project',str(config)],('PUT','/projects/project/collection-config',json.loads(config.read_text()))),
              (['preflight','project'],('POST','/projects/project/preflight',None)),
              (['collect','project','--config-revision','observed'],('POST','/projects/project/jobs',{'stage':'COLLECT','config_revision':'observed'}))]
    for command,expected in commands:
        result=runner.invoke(cli.app,command)
        assert result.exit_code==0,result.output
        assert calls[-1]==expected

def test_cli_bad_json_never_echoes_input(tmp_path,monkeypatch):
    calls=[];monkeypatch.setattr(cli,'request',lambda *args:calls.append(args))
    path=tmp_path/'bad.json';path.write_text('synthetic-secret invalid json')
    result=runner.invoke(cli.app,['register-source',str(path)])
    assert result.exit_code==1 and 'synthetic-secret' not in result.output and not calls

def test_cli_session_credentials_and_proxy_policy(monkeypatch):
    calls=[];real_client=httpx.Client
    monkeypatch.delenv('ALMRAG_API_KEY',raising=False)
    monkeypatch.setenv('ALMRAG_API_URL','https://console.example.invalid')
    monkeypatch.setenv('ALMRAG_SESSION_TOKEN','synthetic-session')
    monkeypatch.setenv('ALMRAG_CSRF_TOKEN','synthetic-csrf')
    def factory(**kwargs):
        calls.append(kwargs)
        return real_client(**kwargs,transport=httpx.MockTransport(lambda r:calls.append(r) or httpx.Response(200,json={'status':'READY'})))
    monkeypatch.setattr(cli.httpx,'Client',factory)
    result=runner.invoke(cli.app,['preflight','project'])
    assert result.exit_code==0,result.output
    assert calls[0]['trust_env'] is False
    req=calls[1]
    assert req.headers['cookie']=='almrag_session=synthetic-session'
    assert req.headers['X-CSRF-Token']=='synthetic-csrf'
    assert req.headers['origin']=='https://console.example.invalid'
    assert 'synthetic-session' not in result.output

def test_cli_rejects_plaintext_session_transmission(monkeypatch):
    monkeypatch.delenv('ALMRAG_API_KEY',raising=False)
    monkeypatch.setenv('ALMRAG_API_URL','http://console.example.invalid')
    monkeypatch.setenv('ALMRAG_SESSION_TOKEN','synthetic-session')
    monkeypatch.setattr(cli.httpx,'Client',lambda **kwargs: (_ for _ in ()).throw(AssertionError('must not send')))
    result=runner.invoke(cli.app,['preflight','project'])
    assert result.exit_code==1 and 'HTTPS' in result.output

def test_cli_login_without_ui_and_session_file_binding(tmp_path,monkeypatch):
    real_client=httpx.Client;calls=[];session=tmp_path/'session.json'
    monkeypatch.setenv('ALMRAG_API_URL','https://console.example.invalid')
    monkeypatch.setenv('ALMRAG_SESSION_FILE',str(session))
    monkeypatch.delenv('ALMRAG_API_KEY',raising=False)
    monkeypatch.delenv('ALMRAG_SESSION_TOKEN',raising=False)
    monkeypatch.setattr(cli.getpass,'getpass',lambda _:'synthetic-password')
    def handler(req):
        calls.append(req)
        if req.url.path.endswith('/login'):
            return httpx.Response(204,headers=[('set-cookie','almrag_session=synthetic-session; Secure; HttpOnly; Path=/api/v1'),('set-cookie','almrag_csrf=synthetic-csrf; Secure; Path=/')])
        assert req.headers['cookie']=='almrag_session=synthetic-session'
        return httpx.Response(200,json={})
    monkeypatch.setattr(cli.httpx,'Client',lambda **kwargs:real_client(**kwargs,transport=httpx.MockTransport(handler)))
    result=runner.invoke(cli.app,['login','--username','admin'])
    assert result.exit_code==0,result.output
    assert 'synthetic-' not in result.output
    assert session.stat().st_mode & 0o777==0o600
    assert runner.invoke(cli.app,['preflight','project']).exit_code==0
    monkeypatch.setenv('ALMRAG_API_URL','https://different.example.invalid')
    result=runner.invoke(cli.app,['preflight','project'])
    assert result.exit_code==1 and len(calls)==2
