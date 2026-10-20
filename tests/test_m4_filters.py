"""SRS-018/009 approved OI-049 exact identity and preserved field filters."""
import pytest
from almrag.retrieval import SearchRequest,SearchError
from test_processing import setup,add_item,execute
from test_retrieval import service,publish


def prepared(setup):
    add_item(setup,item='Opaque-ID',fields=[{'source_field_id':'private','raw_value':None},{'source_field_id':'flag','raw_value':True}])
    add_item(setup,item='other')
    execute(setup);execute(setup,'EMBED');s,d=service(setup);publish(setup,d)
    return s,d


def test_exact_source_and_uid_rank_without_body_or_dense(setup):
    s,d=prepared(setup);p=setup[2]
    d.points={}
    result=s.search({'query':'Opaque-ID','project_uids':[p],'response':{'include_full_item':True}},allowed_projects=[p])
    assert [h['item']['id'] for h in result['results']]==['Opaque-ID']
    uid=result['results'][0]['item_uid']
    assert s.search({'query':uid,'project_uids':[p]},allowed_projects=[p])['results'][0]['item_uid']==uid


def test_metadata_prefilters_before_both_channels_and_type_exact_equality(setup):
    s,d=prepared(setup);p=setup[2]
    original=d.query
    def query(*args,item_uids=None,**kwargs):
        assert item_uids is not None
        points=d.points;d.points={k:v for k,v in points.items() if v['payload']['item_uid'] in item_uids}
        try:return original(*args,**kwargs)
        finally:d.points=points
    d.query=query
    filters={'source_item_ids':['Opaque-ID'],'source_scope_ids':['t1'],'fields':[{'kind':'SOURCE','key':'private','value':None}]}
    result=s.search({'query':'Title','project_uids':[p],'filters':filters,'response':{'include_full_item':True}},allowed_projects=[p])
    assert [h['item']['id'] for h in result['results']]==['Opaque-ID']
    for field in [{'kind':'SOURCE','key':'missing','value':None},{'kind':'SOURCE','key':'flag','value':1}]:
        assert not s.search({'query':'Title','project_uids':[p],'filters':{'fields':[field]}},allowed_projects=[p])['results']


def test_filter_validation_and_legacy_generation_rejected(setup,monkeypatch):
    for filters in [{'item_uids':[]},{'item_uids':['x','x']},{'fields':[{'kind':'SOURCE','key':'x','value':float('nan')}]}]:
        with pytest.raises(ValueError):SearchRequest(query='x',project_uids=['p'],filters=filters)
    import test_retrieval
    monkeypatch.setattr(test_retrieval,'LEXICAL_VERSION','legacy')
    s,d=prepared(setup);p=setup[2]
    with pytest.raises(SearchError,match='REBUILD_REQUIRED'):s.search({'query':'Title','project_uids':[p]},allowed_projects=[p])


@pytest.mark.parametrize('value,expected',[(None,True),(True,False),(1,False),('1',False),({'nested':['all','values']},False)])
def test_source_null_type_and_missing_are_distinct(setup,value,expected):
    s,d=prepared(setup);p=setup[2]
    result=s.search({'query':'Title','project_uids':[p],'filters':{'fields':[{'kind':'SOURCE','key':'private','value':value}]}},allowed_projects=[p])
    assert bool(result['results']) is expected


def test_scope_id_internal_id_and_normalized_title_intersection(setup):
    s,d=prepared(setup);p=setup[2]
    from almrag.storage import canonical_uid
    uid=canonical_uid('item',p,'Opaque-ID')
    result=s.search({'query':'Title','project_uids':[p],'filters':{'item_uids':[uid],'fields':[{'kind':'NORMALIZED','key':'title','value':'Title'}]}},allowed_projects=[p])
    # Fixture title is precisely 'Title'; source Item ID is distinct metadata.
    assert len(result['results'])==1 and result['results'][0]['item_uid']==uid
    assert s.search({'query':'Title','project_uids':[p],'filters':{'source_scope_ids':['foreign']}},allowed_projects=[p])['results']==[]


def test_exact_id_keeps_mandatory_authorization_and_filters(setup):
    s,d=prepared(setup);p=setup[2]
    with pytest.raises(SearchError,match='FORBIDDEN'):
        s.search({'query':'Opaque-ID','project_uids':[p]},allowed_projects=[])
    assert not d.calls
    result=s.search({'query':'Opaque-ID','project_uids':[p],'filters':{'source_item_ids':['other']}},allowed_projects=[p])
    from almrag.storage import canonical_uid
    assert all(h['item_uid']!=canonical_uid('item',p,'Opaque-ID') for h in result['results'])


def test_scope_filter_describes_published_revision_while_selection_uses_current_membership(setup):
    import json
    s,d=prepared(setup);db,_,p,_,_=setup
    # New collection membership is mutable; active immutable envelope is still t1.
    with db.transaction() as c:c.execute("UPDATE collection_memberships SET scope_id='t2' WHERE source_item_id='Opaque-ID'")
    old=s.search({'query':'Title','project_uids':[p],'filters':{'source_item_ids':['Opaque-ID'],'source_scope_ids':['t1']},'response':{'include_full_item':True}},allowed_projects=[p])
    assert len(old['results'])==1 and old['results'][0]['item']['scope_id']=='t1'
    new=s.search({'query':'Title','project_uids':[p],'filters':{'source_item_ids':['Opaque-ID'],'source_scope_ids':['t2']}},allowed_projects=[p])
    assert new['results']==[]
    with db.transaction() as c:c.execute("UPDATE project_selections SET selection_mode='SELECTED',scope_ids='[\"t1\"]' WHERE project_uid=?",(p,))
    assert s.search({'query':'Title','project_uids':[p]},allowed_projects=[p])['total']==1  # only 'other' stays authorized


def test_exact_id_restores_metadata_only_publication_with_zero_chunks(setup):
    from almrag.processing import ProcessingPolicy,FieldRef
    from almrag.indexing import IndexService
    from almrag.queue import Queue
    from test_indexing import MemoryVector
    db,_,p,r,processing=setup
    add_item(setup,item='META-ID',title='Valid nonempty title',description='Preserved description',fields=[{'source_field_id':'optional','raw_value':''}])
    processing.configure(p,ProcessingPolicy(fields=[FieldRef(kind='SOURCE',key='optional')]))
    assert execute(setup)[0]=='SUCCEEDED' and execute(setup,'EMBED')[0]=='SUCCEEDED'
    index=IndexService(db,processing,MemoryVector());index.enqueue(p)
    assert index.run(Queue(db).claim('metadata-only',300))=='SUCCEEDED'
    from almrag.retrieval import SearchService
    class NoDense:
        def query(self,*args,**kw):return []
    search=SearchService(db,lambda _:r,NoDense(),allow_fixture=True)
    result=search.search({'query':'META-ID','project_uids':[p],'response':{'include_full_item':True}},allowed_projects=[p])
    assert len(result['results'])==1
    hit=result['results'][0]
    assert hit['item']['title']=='Valid nonempty title' and hit['matched_chunks']==[]
    assert search.item_detail(p,hit['item_uid'],allowed_projects=[p])['item']==hit['item']
