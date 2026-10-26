// SRS-044/046/058: source and project switches cannot carry hidden source-field policies.
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ApiClient } from './client';
import { Wizard } from './Wizard';
import type { ConsoleContext } from './App';
afterEach(cleanup);
test.each(['project','product'])('clears source fields on %s switch before saving another project',async(switchKind)=>{
 const requests:{url:string;body:Record<string,unknown>}[]=[];
 const fetcher=vi.fn(async(path:RequestInfo|URL,init?:RequestInit)=>{
  const url=String(path),body=init?.body?JSON.parse(String(init.body)):{};requests.push({url,body});
  const data=url.endsWith('/alm-instances')?{instance_uid:'s',source_type:body.source_type,display_name:'Server',base_url:'https://fixture.invalid',api_profile:'fixture',auth_configured:true}:url.endsWith('/s/projects')?[{id:'a',name:'A',url:''},{id:'b',name:'B',url:''}]:url.endsWith('/scopes')?[{id:'t1',name:'T1',kind:'TRACKER'},{id:'w1',name:'W1',kind:'WORK_ITEM_TYPE'}]:url.includes('/fields?')?[{id:url.includes('/a/')?'old-custom':'new-custom',name:'Custom'}]:url.endsWith('/projects')?{project_uid:'p',alm_instance_uid:'s',source_project_id:'b',name:'B'}:{};
  return {ok:true,status:200,json:async()=>data} as Response;
 });
 const ctx:ConsoleContext={client:new ApiClient({},fetcher as typeof fetch),principal:{admin_session:true,permissions:[],project_uids:[]},projects:[],refresh:async()=>{}};
 render(<Wizard ctx={ctx}/>);
 fireEvent.change(screen.getByLabelText('서버 표시명'),{target:{value:'Server'}});fireEvent.change(screen.getByLabelText('서버 기본 URL'),{target:{value:'https://fixture.invalid'}});fireEvent.change(screen.getByLabelText('자격증명 참조'),{target:{value:'env:FIXTURE_TOKEN'}});fireEvent.click(screen.getByRole('button',{name:'서버 저장 · 연결 검증'}));
 const loadFields=async(project:string)=>{fireEvent.change(screen.getByLabelText('원본 프로젝트'),{target:{value:project}});const allBox=await screen.findByRole('checkbox',{name:/^모든 .* 수집$/}) as HTMLInputElement;if(allBox.checked)fireEvent.click(allBox);fireEvent.click(await screen.findByRole('checkbox',{name:/\((t1|w1)\)$/}));const before=requests.filter(r=>r.url.includes('/fields')).length;fireEvent.click(screen.getByRole('button',{name:/필드 불러오기$/}));await waitFor(()=>expect(requests.filter(r=>r.url.includes('/fields')).length).toBe(before+1));await waitFor(()=>expect(requests.some(r=>r.url.includes('/fields?scope_ids='+(screen.queryByText('W1 (w1)')?'w1':'t1')))).toBe(true));};
 await screen.findByRole('option',{name:'A (a)'});await loadFields('a');fireEvent.click(await screen.findByRole('checkbox',{name:'Custom · 원본 old-custom'}));
 if(switchKind==='product') {fireEvent.change(screen.getByLabelText('ALM 종류'),{target:{value:'polarion'}});fireEvent.click(screen.getByRole('button',{name:'서버 저장 · 연결 검증'}));await screen.findByRole('option',{name:'B (b)'});}
 await loadFields('b');await screen.findByRole('checkbox',{name:'Custom · 원본 new-custom'});
 fireEvent.click(screen.getByRole('button',{name:'프로젝트 · 정책 저장'}));await waitFor(()=>expect(requests.some(r=>r.url.endsWith('/processing-config'))).toBe(true));
 expect(requests.find(r=>r.url.endsWith('/processing-config'))!.body.fields).toEqual([{kind:'NORMALIZED',key:'title'},{kind:'NORMALIZED',key:'description'}]);
});

test('source profile table updates and deletes entries',async()=>{
 const source={instance_uid:'s',source_type:'codebeamer',display_name:'Server',base_url:'https://fixture.invalid',api_profile:'cb-rest-v3',auth_configured:true,auth_method:'bearer',auth_ref:'env:TOKEN',ca_bundle_ref:null,username:null};
 const calls:{method?:string;url:string;body?:Record<string,unknown>}[]=[];
 const fetcher=vi.fn(async(path:RequestInfo|URL,init?:RequestInit)=>{
  const url=String(path);calls.push({method:init?.method,url,body:init?.body?JSON.parse(String(init.body)):undefined});
  if(init?.method==='DELETE')return {ok:true,status:204,json:async()=>undefined} as Response;
  const data=init?.method==='PUT'?{...source,...JSON.parse(String(init.body)),ca_bundle_ref:null,username:null}:[source];
  return {ok:true,status:200,json:async()=>data} as Response;
 });
 vi.spyOn(window,'confirm').mockReturnValue(true);
 const ctx:ConsoleContext={client:new ApiClient({},fetcher as typeof fetch),principal:{admin_session:true,permissions:[],project_uids:[]},projects:[],refresh:async()=>{}};
 render(<Wizard ctx={ctx}/>);
 fireEvent.click(screen.getByText('기존 서버 프로필 재사용'));fireEvent.click(screen.getByRole('button',{name:'서버 목록 조회'}));
 fireEvent.change(await screen.findByLabelText('Server 표시명'),{target:{value:'Renamed'}});
 fireEvent.click(screen.getByRole('button',{name:'Server 수정'}));
 await waitFor(()=>expect(calls.find(c=>c.method==='PUT')?.body).toMatchObject({source_type:'codebeamer',display_name:'Renamed',auth_ref:'env:TOKEN'}));
 fireEvent.click(await screen.findByRole('button',{name:'Renamed 삭제'}));
 await waitFor(()=>expect(calls.some(c=>c.method==='DELETE'&&c.url.endsWith('/alm-instances/s'))).toBe(true));
 await waitFor(()=>expect(screen.queryByLabelText('Renamed 표시명')).toBeNull());
});
