import { useState } from 'react';
import type { ConsoleContext, Schema } from './App';
import { useTask } from './ui';
const formatTime=(value?:number|null)=>value==null?'—':new Date(value*1000).toLocaleString('ko-KR',{hour12:false});
/** Admin-only: lists trackers with sync status and adds new ones to an existing project. */
export function ProjectScopes({ctx,project,onJob}:{ctx:ConsoleContext;project:string;onJob:(job:unknown)=>void}) {
 const task=useTask();const [rows,setRows]=useState<Schema['ProjectScope'][]>();const [pick,setPick]=useState<string[]>([]);
 const load=()=>task.run(()=>ctx.client.projectScopes(project),r=>{setRows(r);setPick([]);});
 const addAndSync=()=>task.run(async()=>{const next=await ctx.client.addProjectScopes(project,pick);return {next,job:await ctx.client.sync(project)};},v=>{setRows(v.next);setPick([]);onJob(v.job);});
 const allSelected=rows?.length&&rows.every(r=>r.selected);
 return <details onToggle={e=>{if((e.currentTarget as HTMLDetailsElement).open&&!rows)void load();}}><summary>수집 트래커 관리</summary>{task.notice}{rows&&<><table><thead><tr><th>추가</th><th>트래커</th><th>상태</th><th>Item</th><th>마지막 동기화</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td><input type="checkbox" aria-label={`${r.name} 추가`} disabled={r.selected||task.busy} checked={r.selected||pick.includes(r.id)} onChange={e=>setPick(e.target.checked?[...pick,r.id]:pick.filter(x=>x!==r.id))}/></td><td>{r.name}</td><td>{!r.selected?'미수집':r.last_synced_at==null?'선택됨 · 동기화 대기':'동기화됨'}</td><td>{r.item_count}</td><td>{formatTime(r.last_synced_at)}</td></tr>)}</tbody></table>{allSelected?<p>모든 트래커가 이미 수집 대상입니다.</p>:<button className="primary" disabled={task.busy||!pick.length} onClick={addAndSync}>추가 후 동기화</button>}</>}</details>;
}
