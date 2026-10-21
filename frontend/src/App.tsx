import { useEffect, useRef, useState } from 'react';
import { getHealth } from './health';
import { ApiClient } from './client';
import type { components } from './generated-api';
import { Field, Json, useTask } from './ui';
import { Wizard } from './Wizard';
import { SearchExplorer } from './SearchExplorer';
import { Jobs } from './Jobs';
import { Operations } from './Operations';
import { Evaluation } from './Evaluation';
import './style.css';
export type Schema=components['schemas'];
export type ConsoleContext={client:ApiClient;principal:Schema['PrincipalInfo'];projects:Schema['ProjectInfo'][];refresh:()=>Promise<void>};
export function can(ctx:ConsoleContext,permission:string,project?:string) {return ctx.principal.admin_session||(ctx.principal.permissions.includes(permission)&&(!project||ctx.principal.project_uids.includes(project)));}
const csrf=()=>document.cookie.split('; ').find(s=>s.startsWith('almrag_csrf='))?.slice('almrag_csrf='.length);
export function App() {
 const [health,setHealth]=useState('Checking');const [context,setContext]=useState<ConsoleContext>();const [tab,setTab]=useState('dashboard');
 const [key,setKey]=useState('');const [username,setUsername]=useState('');const [password,setPassword]=useState('');const session=useRef<AbortController|undefined>(undefined);const task=useTask();
 useEffect(()=>{const c=new AbortController();getHealth(c.signal).then(()=>{if(!c.signal.aborted)setHealth('Available');},()=>{if(!c.signal.aborted)setHealth('Unavailable');});return()=>{c.abort();session.current?.abort();};},[]);
 async function connect(kind:'key'|'session') {
  const suppliedKey=key;const suppliedPassword=password;setKey('');setPassword('');session.current?.abort();const controller=new AbortController();session.current=controller;
  await task.run(async()=>{
   if(kind==='session') await new ApiClient({},fetch,controller.signal).login({username,password:suppliedPassword});
   const client=new ApiClient(kind==='key'?{apiKey:suppliedKey}:{csrf:csrf()},fetch,controller.signal);
   const principal=await client.me();const projects=await client.projects();
   const refresh=async()=>{const p=await client.projects();if(!controller.signal.aborted)setContext(old=>old?{...old,projects:p}:old);};
   if(!controller.signal.aborted){setContext({client,principal,projects,refresh});setTab('dashboard');}
  });
 }
 async function disconnect() {if(context?.principal.admin_session)await task.run(()=>context.client.logout());session.current?.abort();setContext(undefined);setTab('dashboard');setKey('');setPassword('');}
 return <div className="shell"><a href="#content" className="skip">본문으로 이동</a><aside className="sidebar"><header><span className="mark" aria-hidden="true">A</span><span>ALM WORKSPACE</span></header><p className="eyebrow">READ-ONLY INTELLIGENCE</p><nav aria-label="주 메뉴">{[['dashboard','프로젝트'],['wizard','서버 등록'],['search','검색 · Explorer'],['jobs','작업 · 실패 목록'],['operations','백업 · 패키지'],['audit','감사 로그'],['evaluation','검색 평가']].map(([id,label])=><button key={id} aria-current={tab===id?'page':undefined} disabled={!context||(id==='wizard'&&!context.principal.admin_session)||(id==='audit'&&!context.principal.admin_session)} onClick={()=>setTab(id)}>{label}</button>)}</nav><p className={'badge '+health.toLowerCase()} role="status">{health}</p><small>Codebeamer &amp; Polarion<br/>원본 ALM 읽기 전용</small></aside>
 <main id="content"><div className="topbar"><span>요구사항 / 통합 작업 공간</span>{context&&<button onClick={disconnect}>연결 해제</button>}</div><h1>ALM RAG</h1>{task.notice}
 {!context?<section className="panel login"><p className="eyebrow">WORKSPACE ACCESS</p><h2>작업 공간 연결</h2><p>자격증명은 브라우저 메모리에서만 사용합니다. ALM 비밀번호 대신 서버에 설정된 자격증명 참조를 사용하세요.</p><form onSubmit={e=>{e.preventDefault();void connect('key');}}><Field label="API 키"><input type="password" value={key} autoComplete="off" onChange={e=>setKey(e.target.value)} required/></Field><button className="primary" disabled={task.busy}>API 키로 연결</button></form><details><summary>관리자 세션으로 연결</summary><form onSubmit={e=>{e.preventDefault();void connect('session');}}><Field label="관리자 이름"><input autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required/></Field><Field label="관리자 비밀번호"><input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></Field><button disabled={task.busy}>관리자 로그인</button></form></details></section>:
 <div key={tab}>{tab==='dashboard'?<Dashboard ctx={context}/>:tab==='wizard'?<Wizard ctx={context}/>:tab==='search'?<SearchExplorer ctx={context}/>:tab==='jobs'?<Jobs ctx={context}/>:tab==='operations'?<Operations ctx={context}/>:tab==='audit'?<Audit ctx={context}/>:<Evaluation ctx={context}/>}</div>}
 <footer>원본 보존 · 명시적 프로젝트 범위 · 검증된 결과</footer></main></div>;
}
function Dashboard({ctx}:{ctx:ConsoleContext}) {
 const task=useTask();const [result,setResult]=useState<unknown>();return <><div className="section-head"><div><p className="eyebrow">PROJECT OVERVIEW</p><h2>프로젝트</h2></div><button disabled={task.busy} onClick={()=>task.run(ctx.refresh)}>새로 고침</button></div>{task.notice}<div className="cards">{ctx.projects.map(p=><section className="panel" key={p.project_uid}><span className="tag">{p.source_project_id}</span><h3>{p.name}</h3><p className="mono">{p.project_uid}</p><button className="primary" disabled={task.busy||!can(ctx,'project_manage',p.project_uid)} onClick={()=>task.run(()=>ctx.client.sync(p.project_uid),setResult)}>동기화 SYNC</button><details><summary>단계별 작업</summary><div className="actions">{(['COLLECT','PROCESS','EMBED','INDEX','REBUILD_INDEX'] as const).map(stage=><button key={stage} disabled={task.busy||!can(ctx,'project_manage',p.project_uid)} onClick={()=>task.run(()=>ctx.client.startJob(p.project_uid,{stage}),setResult)}>{stage}</button>)}</div><button disabled={task.busy||!can(ctx,'project_manage',p.project_uid)} onClick={()=>task.run(()=>ctx.client.pipelinePreflight(p.project_uid),setResult)}>동기화 사전 검증</button></details></section>)}</div>{!ctx.projects.length&&<p className="empty">접근 가능한 프로젝트가 없습니다.</p>}{result!==undefined&&<section className="panel"><h3>작업 응답</h3><Json value={result}/></section>}</>;
}
function Audit({ctx}:{ctx:ConsoleContext}) {const task=useTask();const [rows,setRows]=useState<unknown[]>([]);useEffect(()=>{void task.run(()=>ctx.client.audit(),setRows);},[]);return <section className="panel"><h2>감사 로그</h2>{task.notice}<button disabled={task.busy} onClick={()=>task.run(()=>ctx.client.audit(),setRows)}>로그 새로 고침</button><Json value={rows}/></section>;}
