import { useEffect, useState } from 'react';
import type { ConsoleContext, Schema } from './App';
import { Field, Toggle, useTask } from './ui';

const PAGE = 20;
type Key = Schema['KeyInfo'];
type Created = { name: string; key_id: string; key: string; project_uids: string[]; permissions: string[] };
const copy = (text: string) => navigator.clipboard?.writeText(text);

export function ApiKeyManagement({ ctx }: { ctx: ConsoleContext }) {
 const task = useTask();
 const [items, setItems] = useState<Key[]>([]);
 const [total, setTotal] = useState(0);
 const [offset, setOffset] = useState(0);
 const [nameInput, setNameInput] = useState('');
 const [filter, setFilter] = useState<{ name: string; project: string; status: '' | 'active' | 'revoked' }>({ name: '', project: '', status: '' });
 const [creating, setCreating] = useState(false);
 const [created, setCreated] = useState<Created>();
 const [revoking, setRevoking] = useState<Key>();
 const [message, setMessage] = useState('');
 const projectName = (uid: string) => ctx.projects.find(p => p.project_uid === uid)?.name ?? uid;

 const load = () => task.run(
  () => ctx.client.listKeys({ name: filter.name, project_uid: filter.project, status: filter.status || undefined, limit: PAGE, offset }),
  r => { setItems(r.items); setTotal(r.total); },
 );
 useEffect(() => { void load(); }, [filter, offset]);

 async function revoke() {
  if (!revoking) return;
  const target = revoking;
  await task.run(() => ctx.client.revokeKey(target.key_id), () => { setMessage(`${target.name} Key를 폐기했습니다.`); setRevoking(undefined); void load(); });
 }

 return <>
  <div className="section-head"><div><p className="eyebrow">ADMINISTRATION</p><h2>API Key 관리</h2></div>
   <div className="actions"><button disabled={task.busy} onClick={() => void load()}>목록 새로 고침</button><button className="primary" disabled={creating || !!created} onClick={() => { setCreating(true); setMessage(''); }}>+ 새 API Key 발급</button></div></div>
  {task.notice}{message && <p role="status" className="notice">{message}</p>}
  {creating && !created && <CreateForm ctx={ctx} onCancel={() => setCreating(false)} onCreated={c => { setCreating(false); setCreated(c); setOffset(0); void load(); }} />}
  {created && <CreatedDialog created={created} projectName={projectName} onClose={() => setCreated(undefined)} />}
  {revoking && <section className="panel" role="dialog" aria-label="API Key 폐기 확인">
   <h3>API Key 폐기</h3><p>이 API Key를 폐기하시겠습니까? 폐기하면 해당 Key로 ALM-RAG에 접근할 수 없습니다.</p>
   <p>Name: <strong>{revoking.name}</strong></p><p className="mono wrap">Key ID: {revoking.key_id}</p>
   <div className="actions"><button disabled={task.busy} onClick={() => setRevoking(undefined)}>취소</button><button className="primary" disabled={task.busy} onClick={() => void revoke()}>폐기 확인</button></div></section>}
  <section className="panel">
   <form className="form-grid" onSubmit={e => { e.preventDefault(); setOffset(0); setFilter(f => ({ ...f, name: nameInput.trim() })); }}>
    <Field label="이름 검색"><input value={nameInput} maxLength={128} onChange={e => setNameInput(e.target.value)} /></Field>
    <Field label="프로젝트 필터"><select value={filter.project} onChange={e => { setOffset(0); setFilter(f => ({ ...f, project: e.target.value })); }}><option value="">전체 프로젝트</option>{ctx.projects.map(p => <option key={p.project_uid} value={p.project_uid}>{p.name}</option>)}</select></Field>
    <Field label="상태 필터"><select value={filter.status} onChange={e => { setOffset(0); setFilter(f => ({ ...f, status: e.target.value as typeof f.status })); }}><option value="">전체 상태</option><option value="active">Active</option><option value="revoked">Revoked</option></select></Field>
    <button disabled={task.busy}>검색</button>
   </form>
   {task.busy && !items.length ? <p role="status">불러오는 중…</p> : !items.length ? <p className="empty">발급된 API Key가 없습니다.</p> :
    <div className="table-wrap"><table><thead><tr><th>Name</th><th>Key ID</th><th>Projects</th><th>Permissions</th><th>Created At</th><th>Status</th><th>Action</th></tr></thead><tbody>
     {items.map(k => <tr key={k.key_id}>
      <td className="wrap">{k.name}</td>
      <td className="mono wrap">{k.key_id} <button type="button" aria-label={`${k.name} Key ID 복사`} onClick={() => void copy(k.key_id)}>복사</button></td>
      <td className="wrap">{k.project_uids.map(projectName).join(', ')}</td>
      <td>{k.permissions.join(', ')}</td>
      <td>{k.created_at ? new Date(k.created_at).toLocaleString() : '기록 없음'}</td>
      <td><span className="tag">{k.status === 'active' ? 'Active' : 'Revoked'}</span></td>
      <td>{k.status === 'active' ? <button disabled={task.busy} aria-label={`${k.name} 폐기`} onClick={() => { setRevoking(k); setMessage(''); }}>폐기</button> : '-'}</td></tr>)}
    </tbody></table></div>}
   <div className="actions"><span>전체 {total}개</span><button disabled={task.busy || offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>이전</button><button disabled={task.busy || offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>다음</button></div>
  </section>
 </>;
}

function CreateForm({ ctx, onCancel, onCreated }: { ctx: ConsoleContext; onCancel: () => void; onCreated: (c: Created) => void }) {
 const task = useTask();
 const [name, setName] = useState('');
 const [projects, setProjects] = useState<string[]>([]);
 const [perms, setPerms] = useState<string[]>(['search']);
 const [advanced, setAdvanced] = useState(false);
 const [ack, setAck] = useState(false);
 const toggle = (list: string[], value: string, on: boolean) => on ? [...list, value] : list.filter(v => v !== value);
 const admin = perms.includes('system_admin');
 const invalid = !name.trim() || !projects.length || !perms.length || (admin && !ack);
 return <section className="panel" aria-label="새 API Key 발급">
  <h3>새 API Key 발급</h3>
  {task.notice}
  <form onSubmit={e => { e.preventDefault(); if (invalid || task.busy) return; void task.run(async () => {
    const input = { name: name.trim(), project_uids: projects, permissions: perms as Schema['KeyCreate']['permissions'] };
    return { input, result: await ctx.client.createKey(input) };
   }, ({ input, result }) => onCreated({ name: input.name, key_id: result.key_id, key: result.key, project_uids: input.project_uids, permissions: input.permissions })); }}>
   <Field label="Name"><input required maxLength={128} value={name} onChange={e => setName(e.target.value)} /></Field>
   <fieldset><legend>Accessible Projects</legend>{ctx.projects.map(p => <Toggle key={p.project_uid} label={p.name} checked={projects.includes(p.project_uid)} onChange={v => setProjects(old => toggle(old, p.project_uid, v))} />)}{!ctx.projects.length && <p className="empty">등록된 프로젝트가 없습니다.</p>}</fieldset>
   <fieldset><legend>Permissions</legend>
    {['search', 'project_read', 'project_manage'].map(v => <Toggle key={v} label={v} checked={perms.includes(v)} onChange={on => setPerms(old => toggle(old, v, on))} />)}
    <Toggle label="고급 설정 표시" checked={advanced} onChange={on => { setAdvanced(on); if (!on) { setPerms(old => old.filter(v => v !== 'system_admin')); setAck(false); } }} />
    {advanced && <><Toggle label="system_admin" checked={admin} onChange={on => setPerms(old => toggle(old, 'system_admin', on))} />
     {admin && <Toggle label="system_admin Key는 선택한 프로젝트의 관리 권한을 가지며 신중히 발급해야 함을 확인합니다" checked={ack} onChange={setAck} />}</>}
   </fieldset>
   <div className="actions"><button type="button" onClick={onCancel}>취소</button><button className="primary" disabled={invalid || task.busy}>API Key 생성</button></div>
  </form></section>;
}

function CreatedDialog({ created, projectName, onClose }: { created: Created; projectName: (uid: string) => string; onClose: () => void }) {
 const [shown, setShown] = useState(false);
 return <section className="panel" role="dialog" aria-label="API Key 생성 완료">
  <h3>API Key가 생성되었습니다</h3>
  <p className="warning">보안을 위해 원본 Key는 지금 한 번만 확인할 수 있습니다. 안전한 장소에 저장하세요.</p>
  <p>Name: <strong>{created.name}</strong></p>
  <p className="mono wrap">Key ID: {created.key_id} <button type="button" onClick={() => void copy(created.key_id)}>Key ID 복사</button></p>
  <p>프로젝트: {created.project_uids.map(projectName).join(', ')} · 권한: {created.permissions.join(', ')}</p>
  <Field label="API Key 원문"><input readOnly className="mono" type={shown ? 'text' : 'password'} value={created.key} autoComplete="off" /></Field>
  <div className="actions"><button type="button" onClick={() => setShown(v => !v)}>{shown ? 'API Key 숨기기' : 'API Key 표시'}</button><button type="button" onClick={() => void copy(created.key)}>API Key 복사</button><button className="primary" onClick={onClose}>확인</button></div>
 </section>;
}
