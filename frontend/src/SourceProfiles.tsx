import { useState } from 'react';
import type { ApiClient } from './client';
import type { Schema } from './App';
import { useTask } from './ui';

type Source = Schema['InstanceDetail'];
type Draft = {display_name:string;base_url:string;auth_ref:string;ca_bundle_ref:string;auth_method:'bearer'|'basic';username:string};
const toDraft=(s:Source):Draft=>({display_name:s.display_name,base_url:s.base_url,auth_ref:s.auth_ref,ca_bundle_ref:s.ca_bundle_ref??'',auth_method:s.auth_method,username:s.username??''});
const REF=/^(env:[A-Z][A-Z0-9_]*|vault:[A-Za-z0-9_-]+)$/;

function Row({source,client,busy,onUse,onSaved,onDeleted}:{source:Source;client:ApiClient;busy:boolean;onUse:(s:Source)=>void;onSaved:(s:Source)=>void;onDeleted:(uid:string)=>void}) {
 const task=useTask();const [draft,setDraft]=useState(toDraft(source));
 const codebeamer=source.source_type==='codebeamer';
 const set=<K extends keyof Draft>(key:K,value:Draft[K])=>setDraft(old=>({...old,[key]:value}));
 const label=(name:string)=>`${source.display_name} ${name}`;
 function update() {
  const shared={display_name:draft.display_name,base_url:draft.base_url,auth_ref:draft.auth_ref,...(draft.ca_bundle_ref?{ca_bundle_ref:draft.ca_bundle_ref}:{})};
  const profile=codebeamer?{...shared,source_type:'codebeamer' as const,api_profile:'cb-rest-v3' as const,auth_method:draft.auth_method,...(draft.auth_method==='basic'?{username:draft.username}:{})}:{...shared,source_type:'polarion' as const,api_profile:'polarion-rest-v1' as const,auth_method:'bearer' as const};
  void task.run(()=>client.updateSource(source.instance_uid,profile),s=>{onSaved(s);setDraft(toDraft(s));});
 }
 function remove() {
  if(!window.confirm(`'${source.display_name}' 서버 프로필을 삭제할까요?`))return;
  void task.run(()=>client.deleteSource(source.instance_uid),()=>onDeleted(source.instance_uid));
 }
 const valid=draft.display_name.trim()!==''&&draft.base_url.trim()!==''&&REF.test(draft.auth_ref)&&(!draft.ca_bundle_ref||/^env:[A-Z][A-Z0-9_]*$/.test(draft.ca_bundle_ref))&&(draft.auth_method!=='basic'||draft.username.trim()!=='');
 const off=busy||task.busy;
 return <tr>
  <td><input aria-label={label('표시명')} value={draft.display_name} onChange={e=>set('display_name',e.target.value)}/></td>
  <td>{source.source_type}</td>
  <td><input aria-label={label('기본 URL')} type="url" value={draft.base_url} onChange={e=>set('base_url',e.target.value)}/></td>
  <td><input aria-label={label('자격증명 참조')} value={draft.auth_ref} onChange={e=>set('auth_ref',e.target.value)}/></td>
  <td><input aria-label={label('CA 번들 참조')} value={draft.ca_bundle_ref} onChange={e=>set('ca_bundle_ref',e.target.value)}/></td>
  <td>{codebeamer?<select aria-label={label('인증 방식')} value={draft.auth_method} onChange={e=>set('auth_method',e.target.value as Draft['auth_method'])}><option value="bearer">Bearer</option><option value="basic">Basic</option></select>:'bearer'}</td>
  <td>{codebeamer&&draft.auth_method==='basic'?<input aria-label={label('사용자 이름')} value={draft.username} onChange={e=>set('username',e.target.value)}/>:'-'}</td>
  <td>{source.api_profile}</td>
  <td><button disabled={off} onClick={()=>onUse(source)}>사용</button> <button disabled={off||!valid} onClick={update}>{`${source.display_name} 수정`}</button> <button disabled={off} onClick={remove}>{`${source.display_name} 삭제`}</button>{task.notice}</td>
 </tr>;
}

export function SourceProfiles({type,sources,setSources,client,busy,onUse}:{type:Source['source_type'];sources:Source[];setSources:(next:Source[])=>void;client:ApiClient;busy:boolean;onUse:(s:Source)=>void}) {
 const rows=sources.filter(s=>s.source_type===type);
 if(!rows.length)return null;
 return <div className="table-wrap"><table><caption>등록된 서버 프로필</caption><thead><tr>{['표시명','종류','기본 URL','자격증명 참조','CA 번들 참조','인증 방식','사용자 이름','API 프로필','작업'].map(h=><th key={h} scope="col">{h}</th>)}</tr></thead><tbody>
  {rows.map(s=><Row key={s.instance_uid} source={s} client={client} busy={busy} onUse={onUse} onSaved={next=>setSources(sources.map(o=>o.instance_uid===next.instance_uid?next:o))} onDeleted={uid=>setSources(sources.filter(o=>o.instance_uid!==uid))}/>)}
 </tbody></table></div>;
}
