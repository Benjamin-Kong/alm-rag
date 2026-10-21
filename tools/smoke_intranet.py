"""Synthetic loopback-only Compose HTTP acceptance; never use customer accounts."""
import argparse
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit
import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:18080')
    parser.add_argument('--write-env')
    parser.add_argument('--config-dir',default='/tmp/almrag-intranet-ci-config')
    args=parser.parse_args()
    url=urlsplit(args.url)
    if url.scheme!='http' or url.hostname!='127.0.0.1' or url.path or not url.port or url.username or url.password or url.query or url.fragment:
        parser.error('synthetic smoke requires an explicit loopback HTTP Origin with port')
    if args.write_env:
        path=Path(args.write_env).resolve();config=Path(args.config_dir).resolve()
        config.mkdir(parents=True,exist_ok=True)
        content={
            'ALMRAG_ENV_FILE':str(path),'ALMRAG_CONFIG_DIR':str(config),
            'ALMRAG_INTRANET_HTTP_ENABLED':'true','ALMRAG_ALLOWED_ORIGIN':args.url,
            'ALMRAG_BIND_ADDRESS':'127.0.0.1','ALMRAG_HTTP_PORT':str(url.port),
            'ALMRAG_QDRANT_API_KEY':secrets.token_urlsafe(32),
            'ALMRAG_QDRANT_AUTH_REF':'env:ALMRAG_QDRANT_API_KEY',
            'ALMRAG_QDRANT_URL':'http://qdrant:6333',
            'ALMRAG_LIVE_ALM_ENABLED':'false','ALMRAG_LIVE_MODEL_ENABLED':'false',
            'ALMRAG_LIVE_VECTOR_ENABLED':'false','ALMRAG_NOTION_SUMMARY_ENABLED':'false'}
        # Exclusive creation: never replace an operator configuration file.
        with path.open('x') as stream:
            path.chmod(0o600)
            stream.write(''.join(f'{key}={value}\n' for key,value in content.items()))
        print('SYNTHETIC_ENV_READY')
        return 0
    try:
        with httpx.Client(base_url=args.url,trust_env=False,follow_redirects=False,timeout=5) as client:
            deadline=time.monotonic()+30
            while True:
                try:
                    if client.get('/api/v1/healthz').status_code==200:break
                except httpx.HTTPError:pass
                if time.monotonic()>=deadline:raise ValueError('health timeout')
                time.sleep(.25)
            assert client.get('/').status_code==200
            assert client.get('/api/v1/projects').status_code==401
            response=client.post('/api/v1/auth/login',headers={'Origin':args.url},json={'username':'synthetic-intranet-admin','password':'synthetic intranet password'})
            assert response.status_code==204
            session=next(c for c in client.cookies.jar if c.name=='almrag_session')
            assert not session.secure and session.has_nonstandard_attr('HttpOnly')
            assert client.get('/api/v1/projects').status_code==200
            assert client.post('/api/v1/auth/logout').status_code==403
            csrf=client.cookies['almrag_csrf']
            assert client.post('/api/v1/auth/logout',headers={'Origin':'http://foreign.invalid','X-CSRF-Token':csrf}).status_code==403
            assert client.post('/api/v1/auth/logout',headers={'Origin':args.url,'X-CSRF-Token':csrf}).status_code==204
            assert client.get('/api/v1/projects').status_code==401
    except (httpx.HTTPError,ValueError,AssertionError,StopIteration,KeyError):
        print('INTRANET_HTTP_SMOKE_FAIL')
        return 1
    print('INTRANET_HTTP_SMOKE_PASS health/UI/private API/login/HttpOnly/CSRF/Origin/logout')
    return 0


if __name__=='__main__':raise SystemExit(main())
