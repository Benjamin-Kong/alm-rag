"""Resolve browser links locally; never expose REST self links or credentials."""
from urllib.parse import quote, urlsplit, urlunsplit


def _parts(value):
    if not isinstance(value,str) or any(ord(c)<=32 or ord(c)==127 for c in value) or '\\' in value:
        return None
    try:
        parts=urlsplit(value)
        if parts.scheme not in {'http','https'} or not parts.hostname or parts.username is not None or parts.password is not None:
            return None
        parts.port
        return parts
    except ValueError:
        return None


def item_browser_url(source_type,base_url,project_id,item_id,envelope):
    base=_parts(base_url)
    if base is None or base.query or base.fragment:return None
    path=base.path.rstrip('/')
    if source_type=='codebeamer':
        for suffix in ('/api/v3','/api','/rest','/v3'):
            if path.endswith(suffix):
                path=path[:-len(suffix)];break
        target=path+'/issue/'+quote(item_id,safe='')
    elif source_type=='polarion':
        if path.endswith('/rest/v1'):path=path[:-len('/rest/v1')]
        if not path:path='/polarion'
        target=path+'/redirect/project/'+quote(project_id,safe='')+'/workitem'
    else:return None
    fallback=urlunsplit((base.scheme,base.netloc,target,'id='+quote(item_id,safe='') if source_type=='polarion' else '', ''))
    raw=envelope.get('raw',{})
    resource=raw.get('data',raw) if isinstance(raw,dict) else {}
    links=resource.get('links',{}) if isinstance(resource,dict) else {}
    candidates=[links.get('portal') if isinstance(links,dict) else None,envelope.get('source_url')]
    for candidate in candidates:
        parts=_parts(candidate)
        if parts is None or (parts.scheme,parts.hostname,parts.port)!=(base.scheme,base.hostname,base.port):continue
        # Accept only the canonical Item path/parameters, preserving opaque portal URLs.
        if source_type=='codebeamer':
            valid=parts.path==target and not parts.query and not parts.fragment
        else:
            expected_query='id='+quote(item_id,safe='')
            fragment='/project/'+quote(project_id,safe='')+'/workitem?'+expected_query
            valid=(parts.path==target and parts.query==expected_query and not parts.fragment) or (parts.path==path+'/' and not parts.query and parts.fragment==fragment)
        if valid:return candidate
    return fallback
