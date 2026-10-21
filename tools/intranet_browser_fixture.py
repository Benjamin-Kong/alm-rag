"""Synthetic HTTP browser fixture ONLY; production uses python -m almrag.server."""
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import uvicorn
from almrag.config import Settings
from almrag.server import create_server
from almrag.queue import Queue
from almrag.quality import QualityService
from almrag.worker import run_once


def main():
    root=Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix='almrag-http-browser-') as directory:
        settings=Settings(database_path=str(Path(directory)/'synthetic.sqlite'),allowed_origin='http://127.0.0.1:19444',intranet_http_enabled=True)
        app=create_server(settings,frontend_dist=root/'frontend/dist')
        db=app.api.state.db
        instance=db.add_instance('codebeamer','https://synthetic.invalid','Synthetic HTTP','env:SYNTHETIC_UNUSED')
        db.add_project(instance,'synthetic-http','HTTP browser fixture')
        app.api.state.security.bootstrap('synthetic-http-admin','synthetic browser password')
        done=threading.Event();quality=QualityService(db,attachment_root=Path(directory)/'attachments')
        def work():
            while not done.is_set():
                run_once(Queue(db),'synthetic-http-worker',quality_service=quality)
                done.wait(0.05)
        thread=threading.Thread(target=work,daemon=True);thread.start()
        try:uvicorn.run(app,host='127.0.0.1',port=19444,access_log=False,log_level='warning',proxy_headers=False)
        finally:done.set();thread.join(timeout=5)


if __name__=='__main__':main()
