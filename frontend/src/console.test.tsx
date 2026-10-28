// SRS-025/029/044/058: real Red before the M5 console implementation.
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from './App';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mockApi(permission = ['search','project_read']) {
 const requests: [string,RequestInit|undefined][]=[];
 vi.stubGlobal('fetch',vi.fn(async (path:string,init?:RequestInit) => {
  requests.push([path,init]);
  const data=path.endsWith('healthz')?{status:'ok'}:path.endsWith('/auth/me')?{admin_session:false,permissions:permission,project_uids:['p'],username:null}:path.endsWith('/projects')?[{project_uid:'p',alm_instance_uid:'s',source_project_id:'sp',name:'테스트 프로젝트'}]:path.endsWith('/jobs')?[]:path.endsWith('/search')?{total:1,results:[{item_uid:'i',project_uid:'p',revision_uid:'r',title:'<img src=x onerror=alert(1)>',matched_chunks:[]}],exhausted:true,backfill_limited:false,rounds:1,unindexed_project_uids:[]}:{};
  return {ok:true,status:200,json:async()=>data};
 }));return requests;
}
async function connect() {
 fireEvent.change(screen.getByLabelText('API 키'),{target:{value:'fixture-key'}});
 fireEvent.click(screen.getByRole('button',{name:'API 키로 연결'}));
 await screen.findByText('테스트 프로젝트');
}
test('API key stays in memory and read-only users cannot start jobs',async()=>{
 mockApi();render(<App/>);await connect();
 expect(localStorage.length).toBe(0);expect(sessionStorage.length).toBe(0);
 expect(screen.queryByDisplayValue('fixture-key')).toBeNull();
 expect((screen.getByRole('button',{name:'동기화 SYNC'}) as HTMLButtonElement).disabled).toBe(true);
 expect((screen.getByRole('button',{name:'서버 등록'}) as HTMLButtonElement).disabled).toBe(true);
});
test('search requires explicit project selection and escapes hostile titles',async()=>{
 const requests=mockApi();render(<App/>);await connect();
 fireEvent.click(screen.getByRole('button',{name:'검색 · Explorer'}));
 fireEvent.change(screen.getByLabelText('검색어'),{target:{value:'requirements'}});
 expect((screen.getByRole('button',{name:'검색 실행'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:'테스트 프로젝트'}));
 fireEvent.click(screen.getByRole('button',{name:'검색 실행'}));
 await screen.findByText('<img src=x onerror=alert(1)>');expect(document.querySelector('img')).toBeNull();
 const request=requests.find(([path])=>path.endsWith('/search'))!;
 expect(JSON.parse(request[1]!.body as string).project_uids).toEqual(['p']);
 expect(JSON.parse(request[1]!.body as string)).not.toHaveProperty('filters');
 fireEvent.change(screen.getByLabelText('원본 Item ID 필터 (쉼표 구분)'),{target:{value:'REQ-1, REQ-1'}});
 fireEvent.change(screen.getByLabelText('Scope ID 필터 (쉼표 구분)'),{target:{value:'tracker-2'}});
 fireEvent.click(screen.getByRole('button',{name:'검색 실행'}));
 await waitFor(()=>expect(requests.filter(([path])=>path.endsWith('/search'))).toHaveLength(2));
 const filtered=requests.filter(([path])=>path.endsWith('/search'))[1];
 expect(JSON.parse(filtered[1]!.body as string).filters).toEqual({source_item_ids:['REQ-1'],source_scope_ids:['tracker-2']});
});
test('a forbidden response shows safe text without disclosing the backend body',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>path.endsWith('healthz')?{ok:true,status:200,json:async()=>({status:'ok'})}:{ok:false,status:403,json:async()=>({detail:'private-server-secret'})}));
 render(<App/>);fireEvent.change(screen.getByLabelText('API 키'),{target:{value:'fixture-key'}});fireEvent.click(screen.getByRole('button',{name:'API 키로 연결'}));
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('권한'));
 expect(document.body.textContent).not.toContain('private-server-secret');
});
test('search-only keys land on Search and other menus are disabled',async()=>{
 mockApi(['search']);render(<App/>);await connect();
 expect(screen.getByLabelText('검색어')).toBeTruthy();
 for(const name of ['프로젝트','서버 등록','작업 · 실패 목록','백업 · 패키지','감사 로그','검색 평가'])expect((screen.getByRole('button',{name}) as HTMLButtonElement).disabled).toBe(true);
 expect((screen.getByRole('button',{name:'검색 · Explorer'}) as HTMLButtonElement).disabled).toBe(false);
});
