"""Persistent same-origin UI/API entrypoint. No demo accounts or temporary DB."""
import argparse
import os
from pathlib import Path

from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from almrag.api import create_app
from almrag.config import Settings


class RuntimeServer:
    def __init__(self, api, directory):
        self.api=api
        self.static=StaticFiles(directory=directory,html=True,follow_symlink=False)

    async def __call__(self, scope, receive, send):
        path=scope.get('path','')
        if scope['type']!='http' or path=='/api' or path.startswith('/api/'):
            return await self.api(scope,receive,send)
        # Keep static files outside the API authentication middleware. All API
        # paths, including unknown API routes, still go through that boundary.
        async def send_static(message):
            if message['type']=='http.response.start':
                message['headers']=list(message.get('headers',[]))+[(b'x-content-type-options',b'nosniff'),(b'cache-control',b'no-store')]
            await send(message)
        try:return await self.static(scope,receive,send_static)
        except HTTPException as exc:
            return await Response(status_code=exc.status_code,headers=exc.headers)(scope,receive,send_static)


def create_server(settings=None, *, frontend_dist=None):
    directory=Path(frontend_dist or os.getenv('ALMRAG_FRONTEND_DIST','frontend/dist')).resolve()
    if not directory.is_dir() or not (directory/'index.html').is_file():
        raise ValueError('frontend_build_unavailable')
    return RuntimeServer(create_app(settings or Settings.from_env()),directory)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    import uvicorn
    try:app=create_server()
    except ValueError:
        parser.exit(1,'Runtime configuration or frontend build unavailable. Check configured Origin and frontend/dist.\n')
    uvicorn.run(app,host=args.host,port=args.port,access_log=False,proxy_headers=False)


if __name__=='__main__':main()
