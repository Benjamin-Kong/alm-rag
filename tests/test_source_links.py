"""SRS-014/020/024: source identity and safe browser links on search results."""
import pytest
from almrag.source_links import item_browser_url


@pytest.mark.parametrize('kind,base,project,item,expected', [
    ('codebeamer','https://alm.invalid/cb/api','p','123','https://alm.invalid/cb/issue/123'),
    ('codebeamer','https://alm.invalid','p','a/b?#','https://alm.invalid/issue/a%2Fb%3F%23'),
    ('polarion','https://alm.invalid/polarion/rest/v1','a/b','REQ-1 &x','https://alm.invalid/polarion/redirect/project/a%2Fb/workitem?id=REQ-1%20%26x'),
    ('polarion','https://alm.invalid','p','REQ-1','https://alm.invalid/polarion/redirect/project/p/workitem?id=REQ-1'),
])
def test_browser_links_preserve_context_and_encode_ids(kind,base,project,item,expected):
    assert item_browser_url(kind,base,project,item,{}) == expected


@pytest.mark.parametrize('url', ['javascript:alert(1)','https://evil.invalid/issue/1','https://user:secret@alm.invalid/issue/1','https://alm.invalid/issue/1?token=secret'])
def test_untrusted_source_url_does_not_become_a_navigation_target(url):
    assert item_browser_url('codebeamer','https://alm.invalid','p','1',{'source_url':url}) == 'https://alm.invalid/issue/1'


def test_polarion_portal_link_is_preserved_instead_of_rest_self():
    portal='https://alm.invalid/polarion/#/project/p/workitem?id=REQ-1'
    raw={'data':{'links':{'self':'https://alm.invalid/polarion/rest/v1/projects/p/workitems/REQ-1','portal':portal}}}
    assert item_browser_url('polarion','https://alm.invalid/polarion/rest/v1','p','REQ-1',{'raw':raw}) == portal


@pytest.mark.parametrize('base', ['javascript:alert(1)','https://user:secret@alm.invalid','https://alm.invalid?token=secret','https://alm.invalid:bad','https://alm.invalid/\npath'])
def test_invalid_or_credential_bearing_base_has_no_link(base):
    assert item_browser_url('codebeamer',base,'p','1',{}) is None


@pytest.mark.parametrize('portal', ['https://alm.invalid/polarion/#/project/other/workitem?id=REQ-1','https://alm.invalid/polarion/redirect/project/p/workitem?id=OTHER','https://evil.invalid/polarion/redirect/project/p/workitem?id=REQ-1'])
def test_polarion_portal_cannot_override_item_or_project(portal):
    assert item_browser_url('polarion','https://alm.invalid/polarion/rest/v1','p','REQ-1',{'raw':{'data':{'links':{'portal':portal}}}}) == 'https://alm.invalid/polarion/redirect/project/p/workitem?id=REQ-1'
