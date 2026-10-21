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
  const data=url.endsWith('/alm-instances')?{instance_uid:'s',source_type:body.source_type,display_name:'Server',base_url:'https://fixture.invalid',api_profile:'fixture',auth_configured:true}:url.endsWith('/s/projects')?[{id:'a',name:'A',url:''},{id:'b',name:'B',url:''}]:url.endsWith('/scopes')?[]:url.endsWith('/fields')?[{id:url.includes('/a/')?'old-custom':'new-custom',name:'Custom'}]:url.endsWith('/projects')?{project_uid:'p',alm_instance_uid:'s',source_project_id:'b',name:'B'}:{};
  return {ok:true,status:200,json:async()=>data} as Response;
 });
 const ctx:ConsoleContext={client:new ApiClient({},fetcher as typeof fetch),principal:{admin_session:true,permissions:[],project_uids:[]},projects:[],refresh:async()=>{}};
 render(<Wizard ctx={ctx}/>);
 fireEvent.change(screen.getByLabelText('서버 표시명'),{target:{value:'Server'}});fireEvent.change(screen.getByLabelText('서버 기본 URL'),{target:{value:'https://fixture.invalid'}});fireEvent.change(screen.getByLabelText('자격증명 참조'),{target:{value:'env:FIXTURE_TOKEN'}});fireEvent.click(screen.getByRole('button',{name:'서버 저장 · 연결 검증'}));
 await screen.findByRole('option',{name:'A (a)'});fireEvent.change(screen.getByLabelText('원본 프로젝트'),{target:{value:'a'}});fireEvent.click(await screen.findByRole('checkbox',{name:'Custom · 원본 old-custom'}));
 if(switchKind==='product') {fireEvent.change(screen.getByLabelText('ALM 종류'),{target:{value:'polarion'}});fireEvent.click(screen.getByRole('button',{name:'서버 저장 · 연결 검증'}));await screen.findByRole('option',{name:'B (b)'});}
 fireEvent.change(screen.getByLabelText('원본 프로젝트'),{target:{value:'b'}});await screen.findByRole('checkbox',{name:'Custom · 원본 new-custom'});
 fireEvent.click(screen.getByRole('button',{name:'프로젝트 · 정책 저장'}));await waitFor(()=>expect(requests.some(r=>r.url.endsWith('/processing-config'))).toBe(true));
 expect(requests.find(r=>r.url.endsWith('/processing-config'))!.body.fields).toEqual([{kind:'NORMALIZED',key:'title'},{kind:'NORMALIZED',key:'description'}]);
});
