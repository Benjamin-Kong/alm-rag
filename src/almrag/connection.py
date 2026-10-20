"""Source-discriminated profiles; credential values never enter stored profiles."""
import json
import os
import ssl
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from almrag.alm_http import ALMHttpClient, HttpPolicy, AlmError
from almrag.config import canonical_endpoint,server_origin
from uuid import uuid4
from almrag.security import SecretVault


class Profile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    display_name:str=Field(min_length=1,max_length=200)
    base_url:str
    auth_ref:str=Field(pattern=r'^(env:[A-Z][A-Z0-9_]*|vault:[A-Za-z0-9_-]+)$')
    http_policy:HttpPolicy=Field(default_factory=HttpPolicy)
    ca_bundle_ref:str|None=Field(default=None,pattern=r'^env:[A-Z][A-Z0-9_]*$')

    @field_validator('base_url')
    @classmethod
    def valid_base(cls,value):return canonical_endpoint(value)


class CodebeamerProfile(Profile):
    source_type:Literal['codebeamer']
    api_profile:Literal['cb-rest-v3']='cb-rest-v3'
    auth_method:Literal['bearer','basic']='bearer'
    username:str|None=None

    @model_validator(mode='after')
    def basic_username(self):
        if self.auth_method=='basic' and not self.username:raise ValueError('username_required')
        return self


class PolarionProfile(Profile):
    source_type:Literal['polarion']
    api_profile:Literal['polarion-rest-v1']='polarion-rest-v1'
    auth_method:Literal['bearer']='bearer'


SourceProfileCreate=Annotated[CodebeamerProfile|PolarionProfile,Field(discriminator='source_type')]
PROFILE_ADAPTER=TypeAdapter(SourceProfileCreate)


class Connections:
    def __init__(self,db,settings,transport_factory=None,secret_resolver=None):
        self.db,self.settings=db,settings
        self.transport_factory,self.secret_resolver=transport_factory,secret_resolver

    def register(self,profile):
        with self.db.transaction() as c:
            found=c.execute('SELECT instance_uid FROM instances WHERE source_type=? AND base_url=?',(profile.source_type,profile.base_url)).fetchone()
            uid=found['instance_uid'] if found else str(uuid4())
            c.execute('INSERT INTO instances(instance_uid,source_type,base_url,display_name,auth_ref) VALUES(?,?,?,?,?) ON CONFLICT(instance_uid) DO UPDATE SET display_name=excluded.display_name,auth_ref=excluded.auth_ref',(uid,profile.source_type,profile.base_url,profile.display_name,profile.auth_ref))
            c.execute('INSERT INTO connection_profiles(instance_uid,config,verified_at) VALUES(?,?,NULL) ON CONFLICT(instance_uid) DO UPDATE SET config=excluded.config,verified_at=NULL',(uid,profile.model_dump_json()))
        return self.info(uid)

    def info(self,uid):
        profile=self.profile(uid)
        return {'instance_uid':uid,'source_type':profile.source_type,'display_name':profile.display_name,'base_url':profile.base_url,'api_profile':profile.api_profile,'auth_configured':True}

    def profile(self,uid):
        with self.db.connect() as c:row=c.execute('SELECT config FROM connection_profiles WHERE instance_uid=?',(uid,)).fetchone()
        if row is None:raise AlmError('INSTANCE_NOT_FOUND',False,status=404)
        return PROFILE_ADAPTER.validate_json(row['config'])

    def secret(self,ref):
        if self.secret_resolver:
            try:
                result=self.secret_resolver(ref)
                if isinstance(result,str) and result:return result
            except (ValueError,OSError):pass
            raise AlmError('CREDENTIAL_UNAVAILABLE',True)
        if ref.startswith('env:'):
            result=os.getenv(ref[4:])
            if result:return result
        elif ref.startswith('vault:') and self.settings.master_key:
            try:return SecretVault(self.db,self.settings.master_key).get(ref[6:])
            except ValueError:pass
        raise AlmError('CREDENTIAL_UNAVAILABLE',True)

    def set_policy(self,uid,policy):
        profile=self.profile(uid)
        server_key=server_origin(profile.base_url)
        with self.db.transaction() as c:
            ALMHttpClient.require_canonical_state(c,server_key)
            c.execute('INSERT INTO server_policies VALUES(?,?) ON CONFLICT(server_key) DO UPDATE SET policy=excluded.policy',(server_key,policy.model_dump_json()))
            c.execute('UPDATE server_budgets SET tokens=min(tokens,?) WHERE server_key=?',(policy.burst,server_key))
            for row in c.execute('SELECT instance_uid,config FROM connection_profiles').fetchall():
                existing=PROFILE_ADAPTER.validate_json(row['config'])
                if server_origin(existing.base_url)==server_key:
                    existing.http_policy=policy
                    c.execute('UPDATE connection_profiles SET config=? WHERE instance_uid=?',(existing.model_dump_json(),row['instance_uid']))

    def connector(self,uid):
        from almrag.connectors import CodebeamerConnector,PolarionConnector
        import base64
        profile=self.profile(uid)
        token=self.secret(profile.auth_ref)
        if profile.auth_method=='basic':
            headers={'Authorization':'Basic '+base64.b64encode((profile.username+':'+token).encode()).decode()}
        else:headers={'Authorization':'Bearer '+token}
        verify=True
        if profile.ca_bundle_ref:verify=ssl.create_default_context(cafile=self.secret(profile.ca_bundle_ref))
        transport=self.transport_factory(uid) if self.transport_factory else None
        client=ALMHttpClient(self.db,uid,profile.base_url,policy=profile.http_policy,auth_headers=headers,transport=transport,
                             allow_live=self.settings.live_alm_enabled,allowed_origins=self.settings.allowed_alm_origins,verify=verify)
        # No live renderer verification has been supplied in M2. Both layers deny POST.
        cls=CodebeamerConnector if profile.source_type=='codebeamer' else PolarionConnector
        return cls(client,renderer_verified=False)
