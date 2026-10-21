// SRS-029/041/058: Explorer restores complete originals even before indexing.
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ApiClient } from './client';
import { SafeHtml, SearchExplorer } from './SearchExplorer';
import type { ConsoleContext } from './App';
afterEach(cleanup);
test('structural preview retains tables but removes active content and every source URL/attribute',()=>{
 const {container}=render(<SafeHtml html={'<table onclick="evil()"><tr><td colspan="2">원본 셀</td></tr></table><img src="https://secret.invalid" onerror="evil()"><script>private-secret</script><svg><a href="javascript:evil()">bad</a></svg><a href="https://secret.invalid">링크 내용</a>'}/>);
 expect(screen.getByText('원본 셀')).toBeTruthy();expect(container.querySelector('table')).toBeTruthy();
 expect(container.querySelector('td')?.colSpan).toBe(2);expect(container.querySelector('img,script,svg,a,[onclick],[src],[href]')).toBeNull();
 expect(container.textContent).not.toContain('private-secret');expect(screen.getByText('링크 내용')).toBeTruthy();
});
test('unindexed items can open complete revision originals and choose an HTML field',async()=>{
 const fetcher=vi.fn(async(path:RequestInfo|URL)=>{
 const url=String(path);const status=url.endsWith('/items/i')?404:200;
 const data=url.endsWith('/projects/p/items')?[{item_uid:'i',source_item_id:'REQ-1',active_revision_uid:null,latest_revision_uid:'r',deleted_state:'PRESENT'}]:url.endsWith('/revisions')?[{revision_uid:'r',source_revision:'v1',hash:'abc',item:{description:'<table><tr><td>보존된 셀</td></tr></table>',title:'원본 제목'}}]:[];
 return {ok:status===200,status,json:async()=>data} as Response;
 });
 const ctx:ConsoleContext={client:new ApiClient({},fetcher as typeof fetch),principal:{admin_session:true,permissions:[],project_uids:[]},projects:[{project_uid:'p',alm_instance_uid:'s',source_project_id:'sp',name:'프로젝트'}],refresh:async()=>{}};
 render(<SearchExplorer ctx={ctx}/>);fireEvent.click(screen.getByText('프로젝트 원본 목록'));fireEvent.click(screen.getByRole('button',{name:'프로젝트 원본 조회'}));
 fireEvent.click(await screen.findByRole('button',{name:'REQ-1'}));
 await screen.findByText('아직 활성 인덱스가 없습니다. 보존된 최신 원본을 표시합니다.');
 fireEvent.change(screen.getByLabelText('HTML 원본 필드'),{target:{value:'description'}});
 expect(await screen.findByText('보존된 셀')).toBeTruthy();expect(screen.getAllByText(/"title": "원본 제목"/)).toHaveLength(2);
});

test('oversized HTML preview is refused explicitly while originals remain available',()=>{
 render(<SafeHtml html={'x'.repeat(1048577)}/>);
 expect(screen.getByText('미리보기 크기 한도를 초과했습니다. 전체 내용은 원본 JSON에서 확인하세요.')).toBeTruthy();
});


test('SVG active-content subtree is dropped instead of exposing its script text',()=>{
 const {container}=render(<SafeHtml html={'<svg><script>svg-private-script</script><text>svg-private-text</text></svg><p>본문</p>'}/>);
 expect(container.textContent).toBe('본문');
});
test('unpublished search hit keeps its own project after another project catalog was opened',async()=>{
 const fetcher=vi.fn(async(path:RequestInfo|URL)=>{
 const url=String(path);const status=url.endsWith('/items/ib')?404:200;
 const data=url.endsWith('/projects/a/items')?[{item_uid:'ia',source_item_id:'A-1',latest_revision_uid:'ra',deleted_state:'PRESENT'}]:url.endsWith('/search')?{total:1,results:[{item_uid:'ib',project_uid:'b',revision_uid:'rb',title:'B 검색 결과'}],exhausted:true,backfill_limited:false,rounds:1,unindexed_project_uids:[]}:url.endsWith('/revisions')?[{revision_uid:'rb',source_revision:'v1',hash:'hash-b',item:{title:'B 원본'}}]:[];
 return {ok:status===200,status,json:async()=>data} as Response;
 });
 const ctx:ConsoleContext={client:new ApiClient({},fetcher as typeof fetch),principal:{admin_session:true,permissions:[],project_uids:[]},projects:['a','b'].map(id=>({project_uid:id,alm_instance_uid:'s',source_project_id:id,name:'프로젝트 '+id})),refresh:async()=>{}};
 render(<SearchExplorer ctx={ctx}/>);fireEvent.click(screen.getByText('프로젝트 원본 목록'));fireEvent.click(screen.getByRole('button',{name:'프로젝트 a 원본 조회'}));await screen.findByRole('button',{name:'A-1'});
 fireEvent.change(screen.getByLabelText('검색어'),{target:{value:'test'}});fireEvent.click(screen.getByRole('checkbox',{name:'프로젝트 b'}));fireEvent.click(screen.getByRole('button',{name:'검색 실행'}));fireEvent.click(await screen.findByRole('button',{name:'B 검색 결과'}));
 await screen.findByText('아직 활성 인덱스가 없습니다. 보존된 최신 원본을 표시합니다.');
 expect(screen.getByText('프로젝트 b · Revision rb / v1')).toBeTruthy();
});

test.each([403,500])('detail HTTP %s does not fall back to revision originals',async(status)=>{
 const fetcher=vi.fn(async(path:RequestInfo|URL)=>{
 const url=String(path),code=url.endsWith('/items/i')?status:200;
 const data=url.endsWith('/projects/p/items')?[{item_uid:'i',source_item_id:'REQ-1',latest_revision_uid:'r',deleted_state:'PRESENT'}]:url.endsWith('/revisions')?[{revision_uid:'r',source_revision:'v1',hash:'hash',item:{title:'must-not-render-original'}}]:[];
 return {ok:code===200,status:code,json:async()=>data} as Response;
 });
 const ctx:ConsoleContext={client:new ApiClient({},fetcher as typeof fetch),principal:{admin_session:true,permissions:[],project_uids:[]},projects:[{project_uid:'p',alm_instance_uid:'s',source_project_id:'sp',name:'프로젝트'}],refresh:async()=>{}};
 render(<SearchExplorer ctx={ctx}/>);fireEvent.click(screen.getByText('프로젝트 원본 목록'));fireEvent.click(screen.getByRole('button',{name:'프로젝트 원본 조회'}));fireEvent.click(await screen.findByRole('button',{name:'REQ-1'}));
 await screen.findByRole('alert');expect(document.body.textContent).not.toContain('must-not-render-original');expect(screen.queryByText('아직 활성 인덱스가 없습니다. 보존된 최신 원본을 표시합니다.')).toBeNull();
});
