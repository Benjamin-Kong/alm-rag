"""Explicit, read-only service capability probes. No calls on construction."""
import ssl
import httpx


class ServiceProbe:
    def __init__(self, settings, secret_resolver=None, transport=None):
        self.settings = settings
        self.secret_resolver = secret_resolver
        self.transport = transport

    def check(self, service):
        if service not in {'ollama','qdrant'}:
            raise ValueError('unsupported_service')
        ref=getattr(self.settings,service+'_auth_ref')
        headers={}
        try:
            if ref:
                if self.secret_resolver is None:
                    return {'service':service,'available':False}
                secret=self.secret_resolver(ref)
                headers['Authorization' if service=='ollama' else 'api-key'] = 'Bearer '+secret if service=='ollama' else secret
            verify=ssl.create_default_context(cafile=self.settings.ca_bundle) if self.settings.tls_verify else False
            url=getattr(self.settings,service+'_url')+('/api/tags' if service=='ollama' else '/healthz')
            with httpx.Client(verify=verify,transport=self.transport,timeout=5,follow_redirects=False,trust_env=False) as client:
                response=client.get(url,headers=headers)
                available=response.status_code==200
        except (httpx.HTTPError,ValueError,OSError):
            available=False
        return {'service':service,'available':available}
