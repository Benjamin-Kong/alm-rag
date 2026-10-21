"""Allowlisted Git summary outbox. Remote publication is disabled by default."""
import hashlib,json,time
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from almrag.alm_http import _SlotLock

class Summary(BaseModel):
    model_config=ConfigDict(extra='forbid')
    commit:str=Field(pattern=r'^(?:[0-9a-f]{40}|[0-9a-f]{64})$')
    milestone:Literal['M1','M2','M3','M4','M5','M6']
    status:Literal['IN_PROGRESS','QUALITY_REVIEW','LOCAL_PASS_WITH_LIMITATIONS','FAIL','NOT_VERIFIED']
    srs_ids:list[str]=Field(min_length=1,max_length=59)
    passed:int=Field(ge=0,le=10000000)
    failed:int=Field(ge=0,le=10000000)
    not_verified:int=Field(ge=0,le=10000000)

    @model_validator(mode='after')
    def ids(self):
        permitted={f'SRS-{n:03}' for n in range(1,60)}
        if not set(self.srs_ids)<=permitted or len(set(self.srs_ids))!=len(self.srs_ids):raise ValueError('known unique SRS IDs required')
        self.srs_ids=sorted(self.srs_ids);return self

class SummaryOutbox:
    def __init__(self,db,*,send=None,enabled=False):
        self.db,self.send,self.enabled=db,send,enabled

    def enqueue(self,summary):
        payload=Summary.model_validate(summary).model_dump_json()
        uid=hashlib.sha256(payload.encode()).hexdigest()
        with self.db.transaction() as c:
            c.execute('INSERT OR IGNORE INTO doc_summary_outbox(summary_uid,payload,created_at) VALUES(?,?,?)',(uid,payload,time.time()))
        return uid

    def flush(self,limit=100):
        if type(limit) is not int or not 1<=limit<=1000:raise ValueError('bounded limit required')
        report={'sent':0,'failed':0,'disabled':not self.enabled or self.send is None}
        if report['disabled']:return report
        lock=_SlotLock(self.db.path.with_suffix('.summary-lock'))
        if not lock.acquire():
            lock.close();return report
        try:
            with self.db.connect() as c:rows=c.execute("SELECT summary_uid,payload FROM doc_summary_outbox WHERE state='PENDING' ORDER BY created_at,summary_uid LIMIT ?",(limit,)).fetchall()
            for row in rows:
                payload=Summary.model_validate_json(row['payload']).model_dump()
                try:self.send(payload)
                except Exception:
                    with self.db.transaction() as c:c.execute("UPDATE doc_summary_outbox SET attempts=attempts+1,error_code='PUBLISH_RETRY_PENDING' WHERE summary_uid=?",(row['summary_uid'],))
                    report['failed']+=1
                else:
                    with self.db.transaction() as c:c.execute("UPDATE doc_summary_outbox SET state='SENT',attempts=attempts+1,error_code=NULL,sent_at=? WHERE summary_uid=?",(time.time(),row['summary_uid']))
                    report['sent']+=1
            return report
        finally:lock.close()


class NotionSummarySender:
    """Append an allowlisted summary to the configured root, with retry lookup.

    Official block-children API; fixed host, TLS verification, no redirects/proxy.
    Network requires explicit opt-in. MockTransport does not contact Notion.
    """
    def __init__(self,root_page,secret_resolver,*,transport=None,allow_network=False):
        from uuid import UUID
        self.root=str(UUID(root_page));self.secret_resolver=secret_resolver
        self.transport,self.allow_network=transport,allow_network

    def __call__(self,payload):
        import httpx
        if self.transport is None and not self.allow_network:raise ValueError('PUBLISH_NETWORK_DISABLED')
        summary=Summary.model_validate(payload).model_dump_json()
        marker='ALM-RAG-SUMMARY:'+hashlib.sha256(summary.encode()).hexdigest()
        text=marker+'\n'+summary
        try:
            secret=self.secret_resolver()
            if not isinstance(secret,str) or not secret:raise ValueError('missing credential')
            with httpx.Client(transport=self.transport,timeout=10,follow_redirects=False,trust_env=False,
                              headers={'Authorization':'Bearer '+secret,'Notion-Version':'2022-06-28'}) as client:
                path='https://api.notion.com/v1/blocks/'+self.root+'/children'
                def request(method,**kwargs):
                    with client.stream(method,path,**kwargs) as response:
                        if response.status_code!=200:raise ValueError('remote rejected')
                        content=bytearray()
                        for part in response.iter_bytes():
                            if len(content)+len(part)>2*1024*1024:raise ValueError('response too large')
                            content.extend(part)
                    value=json.loads(content)
                    if not isinstance(value,dict):raise ValueError('invalid response')
                    return value
                cursor=None;seen=set()
                for _ in range(100):
                    params={'page_size':100}
                    if cursor:params['start_cursor']=cursor
                    page=request('GET',params=params)
                    if not isinstance(page.get('results'),list) or type(page.get('has_more')) is not bool:raise ValueError('invalid page')
                    for block in page['results']:
                        chunks=block.get('paragraph',{}).get('rich_text',[])
                        existing=''.join(t.get('plain_text',t.get('text',{}).get('content','')) for t in chunks)
                        if existing.startswith(marker+'\n'):return
                    if not page['has_more']:break
                    cursor=page.get('next_cursor')
                    if not isinstance(cursor,str) or not cursor or cursor in seen:raise ValueError('invalid cursor')
                    seen.add(cursor)
                else:raise ValueError('deduplication scan bound exceeded')
                rich=[{'type':'text','text':{'content':text[i:i+1900]}} for i in range(0,len(text),1900)]
                request('PATCH',json={'children':[{'object':'block','type':'paragraph','paragraph':{'rich_text':rich}}]})
        except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError,OSError):
            raise ValueError('PUBLISH_UNAVAILABLE') from None
