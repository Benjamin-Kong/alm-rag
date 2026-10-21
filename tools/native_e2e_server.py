"""Loopback-only disposable HTTPS fixture for actual browser/API/session/worker tests.

Never opens an existing database or contacts ALM/model/vector services. Test-only
certificate/private key and synthetic credentials live in a temporary directory.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime,timedelta,timezone
import ipaddress
import threading
import time
import uvicorn
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes,serialization
from fastapi.staticfiles import StaticFiles
from almrag.api import create_app
from almrag.config import Settings
from almrag.storage import Database
from almrag.queue import Queue
from almrag.worker import run_once


def main():
    root=Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix='almrag-native-e2e-') as temporary:
        directory=Path(temporary);db=Database(directory/'synthetic.sqlite');db.migrate()
        instance=db.add_instance('codebeamer','https://synthetic.invalid','Synthetic','env:SYNTHETIC_UNUSED')
        db.add_project(instance,'synthetic-project','Native HTTPS fixture')
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'127.0.0.1')]);now=datetime.now(timezone.utc)
        cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256())
        private=directory/'key.pem';public=directory/'cert.pem'
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));private.chmod(0o600)
        public.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        app=create_app(Settings(database_path=str(db.path),allowed_origin='https://127.0.0.1:19443'),db=db)
        app.state.security.bootstrap('synthetic-admin','synthetic browser password')
        static=StaticFiles(directory=root/'frontend/dist',html=True)
        async def fixture(scope,receive,send):
            if scope['type']=='http' and not scope.get('path','').startswith('/api/v1/'):
                return await static(scope,receive,send)
            return await app(scope,receive,send)
        done=threading.Event()
        def work():
            from almrag.quality import QualityService
            quality=QualityService(db,attachment_root=directory/'attachments')
            while not done.is_set():
                run_once(Queue(db),'synthetic-browser-worker',quality_service=quality)
                done.wait(0.05)
        worker=threading.Thread(target=work,daemon=True);worker.start()
        try:uvicorn.run(fixture,host='127.0.0.1',port=19443,ssl_certfile=str(public),ssl_keyfile=str(private),access_log=False,log_level='warning')
        finally:done.set();worker.join(timeout=5)

if __name__=='__main__':main()
