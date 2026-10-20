"""Lazy configured vector adapter; neither construction nor health contacts Qdrant."""
import ssl
from almrag.connection import Connections
from almrag.vector_store import VectorStore,VectorError


class VectorRuntimeRegistry:
    def __init__(self,settings,db=None,*,secret_resolver=None,transport=None):
        self.settings,self.db,self.secret_resolver,self.transport=settings,db,secret_resolver,transport
        self.abort_check=lambda:False

    def _client(self):
        headers={}
        if self.settings.qdrant_auth_ref:
            resolver=self.secret_resolver or (Connections(self.db,self.settings).secret if self.db is not None else None)
            try:secret=resolver(self.settings.qdrant_auth_ref) if resolver is not None else None
            except (ValueError,OSError):raise VectorError('VECTOR_CREDENTIAL_UNAVAILABLE') from None
            if not isinstance(secret,str) or not secret:raise VectorError('VECTOR_CREDENTIAL_UNAVAILABLE')
            headers['api-key']=secret
        try:verify=ssl.create_default_context(cafile=self.settings.ca_bundle) if self.settings.tls_verify else False
        except (ValueError,OSError):raise VectorError('VECTOR_TLS_CONFIG_INVALID') from None
        return VectorStore(self.settings.qdrant_url,auth_headers=headers,verify=verify,transport=self.transport,allow_live=self.settings.live_vector_enabled,abort_check=self.abort_check)

    def __getattr__(self,name):
        if name not in {'ensure_collection','upsert','retrieve','query','delete_collection'}:raise AttributeError(name)
        def invoke(*args,**kwargs):return getattr(self._client(),name)(*args,**kwargs)
        return invoke
