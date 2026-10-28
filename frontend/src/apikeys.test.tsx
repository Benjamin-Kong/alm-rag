// Admin API key management UI: admin-only menu, list/create/revoke flows and one-time secret handling.
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './App';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const keys=[{key_id:'k-1',name:'user01',project_uids:['p'],permissions:['search'],created_at:'2026-10-28T00:00:00Z',status:'active'},{key_id:'k-0',name:'old',project_uids:['p'],permissions:['search'],created_at:null,status:'revoked'}];
function mockApi(admin:boolean,failCreate=false) {
 const requests:[string,RequestInit|undefined][]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  requests.push([path,init]);const method=init?.method??'GET';
  let data:unknown={};let status=200;
  if(path.endsWith('healthz'))data={status:'ok'};
  else if(path.endsWith('/auth/login'))status=204;
  else if(path.endsWith('/auth/me'))data={admin_session:admin,permissions:admin?[]:['search'],project_uids:['p'],username:admin?'admin':null};
  else if(path.endsWith('/projects'))data=[{project_uid:'p',alm_instance_uid:'s',source_project_id:'sp',name:'테스트 프로젝트'}];
  else if(path.startsWith('/api/v1/api-keys')&&method==='GET')data={items:keys,total:2};
  else if(path.startsWith('/api/v1/api-keys')&&method==='POST'){if(failCreate)return {ok:false,status:404,json:async()=>({})};status=201;data={key_id:'k-2',key:'raw-secret-key'};}
  else if(method==='DELETE')status=204;
  return {ok:true,status,json:async()=>data};
 }));return requests;
}
async function connectAdmin() {
 fireEvent.click(screen.getByText('관리자 세션으로 연결'));
 fireEvent.change(screen.getByLabelText('관리자 이름'),{target:{value:'admin'}});
 fireEvent.change(screen.getByLabelText('관리자 비밀번호'),{target:{value:'long synthetic password'}});
 fireEvent.click(screen.getByRole('button',{name:'관리자 로그인'}));
 await screen.findByText('테스트 프로젝트');
}
test('menu is shown to administrators only',async()=>{
 mockApi(false);render(<App/>);
 fireEvent.change(screen.getByLabelText('API 키'),{target:{value:'fixture-key'}});fireEvent.click(screen.getByRole('button',{name:'API 키로 연결'}));
 await screen.findByText('테스트 프로젝트');expect(screen.queryByRole('button',{name:'API Key 관리'})).toBeNull();
});
test('admin lists, creates (secret shown once) and revokes keys',async()=>{
 const requests=mockApi(true);render(<App/>);await connectAdmin();
 fireEvent.click(screen.getByRole('button',{name:'API Key 관리'}));
 await screen.findByText('user01');expect(screen.getByText('기록 없음')).toBeTruthy();expect(document.body.textContent).not.toContain('key_hash');
 fireEvent.click(screen.getByRole('button',{name:'+ 새 API Key 발급'}));
 const form=screen.getByRole('region',{name:'새 API Key 발급'});
 const submit=within(form).getByRole('button',{name:'API Key 생성'}) as HTMLButtonElement;expect(submit.disabled).toBe(true);
 fireEvent.change(within(form).getByLabelText('Name'),{target:{value:'user03'}});expect(submit.disabled).toBe(true);
 fireEvent.click(within(form).getByLabelText('테스트 프로젝트'));expect(submit.disabled).toBe(false);
 expect(within(form).queryByLabelText('system_admin')).toBeNull();
 fireEvent.click(submit);
 const dialog=await screen.findByRole('dialog',{name:'API Key 생성 완료'});
 const write=vi.fn().mockResolvedValue(undefined);Object.assign(navigator,{clipboard:{writeText:write}});
 const input=within(dialog).getByLabelText('API Key 원문') as HTMLInputElement;expect(input.type).toBe('password');
 fireEvent.click(within(dialog).getByRole('button',{name:'API Key 표시'}));expect(input.type).toBe('text');
 fireEvent.click(within(dialog).getByRole('button',{name:'API Key 복사'}));expect(write).toHaveBeenCalledWith('raw-secret-key');
 const post=requests.find(([,i])=>i?.method==='POST'&&String(i.body).includes('user03'))!;expect(JSON.parse(String(post[1]!.body))).toEqual({name:'user03',project_uids:['p'],permissions:['search']});
 fireEvent.click(within(dialog).getByRole('button',{name:'확인'}));
 expect(document.body.textContent).not.toContain('raw-secret-key');expect(localStorage.length).toBe(0);expect(sessionStorage.length).toBe(0);
 fireEvent.click(screen.getByRole('button',{name:'user01 폐기'}));
 let confirm=screen.getByRole('dialog',{name:'API Key 폐기 확인'});expect(confirm.textContent).toContain('k-1');
 fireEvent.click(within(confirm).getByRole('button',{name:'취소'}));expect(screen.queryByRole('dialog')).toBeNull();
 expect(requests.some(([,i])=>i?.method==='DELETE')).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'user01 폐기'}));
 confirm=screen.getByRole('dialog',{name:'API Key 폐기 확인'});fireEvent.click(within(confirm).getByRole('button',{name:'폐기 확인'}));
 await waitFor(()=>expect(requests.some(([p,i])=>p==='/api/v1/api-keys/k-1'&&i?.method==='DELETE')).toBe(true));
 expect(screen.queryByRole('button',{name:'old 폐기'})).toBeNull();
});
test('create failure shows a safe error',async()=>{
 mockApi(true,true);render(<App/>);await connectAdmin();
 fireEvent.click(screen.getByRole('button',{name:'API Key 관리'}));await screen.findByText('user01');
 fireEvent.click(screen.getByRole('button',{name:'+ 새 API Key 발급'}));
 const form=screen.getByRole('region',{name:'새 API Key 발급'});
 fireEvent.change(within(form).getByLabelText('Name'),{target:{value:'x'}});fireEvent.click(within(form).getByLabelText('테스트 프로젝트'));
 fireEvent.click(within(form).getByRole('button',{name:'API Key 생성'}));
 expect((await within(form).findByRole('alert')).textContent).toContain('찾을 수 없');
});
