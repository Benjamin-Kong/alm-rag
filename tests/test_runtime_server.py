"""SRS025/027/038/051/059: persistent same-origin UI without demo state."""
import importlib
import pytest
from fastapi.testclient import TestClient
from almrag.config import Settings


def test_persistent_ui_dispatch_keeps_api_private_and_no_demo_admin(tmp_path):
    module=importlib.import_module('almrag.server')
    dist=tmp_path/'dist';dist.mkdir();(dist/'index.html').write_text('<h1>synthetic built UI</h1>')
    settings=Settings(database_path=str(tmp_path/'data/live.sqlite'),allowed_origin='http://intranet.test:8080',intranet_http_enabled=True)
    app=module.create_server(settings,frontend_dist=dist)
    with TestClient(app,base_url=settings.allowed_origin) as client:
        response=client.get('/')
        assert response.status_code==200 and 'synthetic built UI' in response.text
        assert client.get('/api/v1/healthz').status_code==200
        assert client.get('/api/v1/projects').status_code==401
        assert client.get('/api/unknown').status_code==401
        assert client.get('/../data/live.sqlite').status_code==404
        assert client.get('/%2e%2e/data/live.sqlite').status_code==404
        assert client.get('/.env').status_code==404
        assert client.post('/api/v1/auth/login',json={'username':'synthetic-admin','password':'synthetic browser password'},headers={'Origin':settings.allowed_origin}).status_code==401
    # Existing DB is reused; no temporary synthetic bootstrap or cleanup.
    from almrag.security import Security
    from almrag.storage import Database
    db=Database(settings.database_path);Security(db).bootstrap('real-test-admin','synthetic persistent password')
    with TestClient(module.create_server(settings,frontend_dist=dist),base_url=settings.allowed_origin) as client:
        response=client.post('/api/v1/auth/login',json={'username':'real-test-admin','password':'synthetic persistent password'},headers={'Origin':settings.allowed_origin})
        assert response.status_code==204
        assert client.get('/api/v1/projects').status_code==200
    assert db.path.exists()


def test_server_rejects_missing_frontend_build(tmp_path):
    module=importlib.import_module('almrag.server')
    with pytest.raises(ValueError,match='frontend_build_unavailable'):
        module.create_server(Settings(database_path=str(tmp_path/'unused.sqlite')),frontend_dist=tmp_path/'absent')
    assert not (tmp_path/'unused.sqlite').exists()
