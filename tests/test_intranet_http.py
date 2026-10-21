"""SRS-019/027/038/051/059: explicitly approved intranet HTTP, same ACL/CSRF."""
import pytest
from fastapi.testclient import TestClient
from almrag.api import create_app
from almrag.config import Settings


def test_http_origin_requires_explicit_opt_in():
    with pytest.raises(ValueError,match='http_origin_requires_intranet_opt_in'):
        Settings(allowed_origin='http://intranet.example.invalid:8080')


def test_intranet_http_env_is_explicit_and_rejects_typo(monkeypatch):
    monkeypatch.setenv('ALMRAG_ALLOWED_ORIGIN','http://intranet.example.invalid:8080')
    monkeypatch.setenv('ALMRAG_INTRANET_HTTP_ENABLED','true')
    assert Settings.from_env().intranet_http_enabled is True
    monkeypatch.setenv('ALMRAG_INTRANET_HTTP_ENABLED','treu')
    with pytest.raises(ValueError,match='invalid_intranet_http_flag'):
        Settings.from_env()


@pytest.mark.parametrize('origin,secure',[
    ('http://intranet.example.invalid:8080',False),
    ('https://intranet.example.invalid:8443',True),
])
def test_cookie_roundtrip_preserves_csrf_acl_and_logout(tmp_path,origin,secure):
    settings=Settings(database_path=str(tmp_path/'intranet.sqlite'),allowed_origin=origin,intranet_http_enabled=True)
    app=create_app(settings)
    app.state.security.bootstrap('test-admin','synthetic intranet password')
    with TestClient(app,base_url=origin) as client:
        payload={'username':'test-admin','password':'synthetic intranet password'}
        assert client.post('/api/v1/auth/login',json=payload,headers={'Origin':'http://foreign.invalid'}).status_code==403
        response=client.post('/api/v1/auth/login',json=payload,headers={'Origin':origin})
        assert response.status_code==204
        cookies=response.headers.get_list('set-cookie')
        session=next(c for c in cookies if c.startswith('almrag_session='))
        assert ('; Secure' in session)==secure
        assert 'HttpOnly' in session and 'SameSite=strict' in session and 'Path=/api/v1' in session
        assert client.get('/api/v1/projects').status_code==200
        assert client.post('/api/v1/auth/logout').status_code==403
        csrf=client.cookies['almrag_csrf']
        assert client.post('/api/v1/auth/logout',headers={'Origin':'http://foreign.invalid','X-CSRF-Token':csrf}).status_code==403
        headers={'Origin':origin,'X-CSRF-Token':csrf}
        assert client.post('/api/v1/auth/logout',headers=headers).status_code==204
        assert not client.cookies.get('almrag_session')
        assert client.get('/api/v1/projects').status_code==401


def test_https_default_still_secure(tmp_path):
    app=create_app(Settings(database_path=str(tmp_path/'default.sqlite'),allowed_origin='https://testserver'))
    app.state.security.bootstrap('admin','synthetic default password')
    with TestClient(app,base_url='https://testserver') as client:
        response=client.post('/api/v1/auth/login',json={'username':'admin','password':'synthetic default password'},headers={'Origin':'https://testserver'})
        assert '; Secure' in response.headers['set-cookie']


def test_cli_http_login_and_requests_need_explicit_matching_origin(tmp_path,monkeypatch):
    import httpx
    from typer.testing import CliRunner
    from almrag import cli
    real_client=httpx.Client;calls=[]
    base='http://intranet.example.invalid:8080'
    monkeypatch.setenv('ALMRAG_API_URL',base)
    monkeypatch.setenv('ALMRAG_ALLOWED_ORIGIN',base)
    monkeypatch.setenv('ALMRAG_INTRANET_HTTP_ENABLED','true')
    monkeypatch.setenv('ALMRAG_SESSION_FILE',str(tmp_path/'session.json'))
    monkeypatch.delenv('ALMRAG_API_KEY',raising=False)
    monkeypatch.delenv('ALMRAG_SESSION_TOKEN',raising=False)
    monkeypatch.setattr(cli.getpass,'getpass',lambda _:'synthetic intranet password')
    def handle(request):
        calls.append(request)
        if request.url.path.endswith('/login'):
            return httpx.Response(204,headers=[('set-cookie','almrag_session=synthetic-session; HttpOnly; SameSite=strict; Path=/api/v1'),('set-cookie','almrag_csrf=synthetic-csrf; Path=/')])
        assert request.headers['Origin']==base
        assert request.headers['X-CSRF-Token']=='synthetic-csrf'
        return httpx.Response(200,json={'status':'READY'})
    monkeypatch.setattr(cli.httpx,'Client',lambda **kwargs:real_client(**kwargs,transport=httpx.MockTransport(handle)))
    runner=CliRunner()
    response=runner.invoke(cli.app,['login'])
    assert response.exit_code==0,response.output
    assert runner.invoke(cli.app,['preflight','project']).exit_code==0
    monkeypatch.setenv('ALMRAG_ALLOWED_ORIGIN','http://different.invalid:8080')
    assert runner.invoke(cli.app,['preflight','project']).exit_code==1
    assert len(calls)==2
