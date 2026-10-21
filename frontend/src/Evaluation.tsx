import { useRef,useState } from 'react';
import { can,type ConsoleContext,type Schema } from './App';
import { Field,Json,useTask } from './ui';
export function Evaluation({ctx}:{ctx:ConsoleContext}){
 const revision=useRef(0);const task=useTask();const [project,setProject]=useState(ctx.projects[0]?.project_uid??'');const [query,setQuery]=useState('');const [relevant,setRelevant]=useState('');const [dataset,setDataset]=useState<Schema['DatasetInfo']>();const [job,setJob]=useState('');const [result,setResult]=useState<unknown>();const [topK,setTopK]=useState(10);
 const manageable=!!project&&can(ctx,'project_manage',project);const ids=relevant.split('\n').map(x=>x.trim()).filter(Boolean);const valid=query.trim()&&ids.length>0&&ids.length<=1000&&new Set(ids).size===ids.length;
 function invalidate(){revision.current++;setDataset(undefined);setJob('');setResult(undefined);}
 return <section className="panel"><p className="eyebrow">QUALITY & EVALUATION</p><h2>무결성 · 검색 평가</h2>{task.notice}<p>골든셋은 프로젝트별로 보관합니다. 실제 작업이 완료된 보고서만 표시합니다. 합성 데이터 지표는 실제 모델의 검색 품질을 보장하지 않습니다.</p>
 <Field label="품질 검사 프로젝트"><select value={project} onChange={e=>{setProject(e.target.value);invalidate();}}><option value="">프로젝트 선택</option>{ctx.projects.map(p=><option key={p.project_uid} value={p.project_uid}>{p.name}</option>)}</select></Field>
 <button disabled={task.busy||!manageable} onClick={()=>{const pin=revision.current;void task.run(()=>ctx.client.integrity(project),v=>{if(pin===revision.current){setJob(v.job_id);setResult(v);}});}}>무결성 검사</button>
 <Field label="평가 검색어"><input value={query} maxLength={65536} onChange={e=>{setQuery(e.target.value);invalidate();}}/></Field>
 <Field label="정답 Item UID (한 줄에 하나)"><textarea value={relevant} onChange={e=>{setRelevant(e.target.value);invalidate();}}/></Field>
 <Field label="평가 K"><input type="number" min="1" max="100" value={topK} onChange={e=>setTopK(+e.target.value)}/></Field>
 <div className="actions"><button disabled={task.busy||!manageable||!valid} onClick={()=>{const pin=revision.current;void task.run(()=>ctx.client.stageEvaluation(project,{cases:[{query,relevant_item_uids:ids}]}),v=>{if(pin===revision.current)setDataset(v);});}}>골든셋 저장</button><button disabled={task.busy||!manageable||!dataset||topK<1||topK>100||!Number.isInteger(topK)} onClick={()=>{const pin=revision.current;if(dataset)void task.run(()=>ctx.client.evaluate(project,dataset.dataset_ref,topK),v=>{if(pin===revision.current){setJob(v.job_id);setResult(v);}});}}>세 검색 방식 평가</button></div>
 {dataset&&<p>검증된 골든셋 · {dataset.case_count}개 쿼리 · {dataset.dataset_ref}</p>}
 <Field label="보고서 작업 ID"><input value={job} onChange={e=>{revision.current++;setJob(e.target.value);setResult(undefined);}}/></Field><button disabled={task.busy||!job||!can(ctx,'project_read',project)} onClick={()=>{const pin=revision.current;void task.run(()=>ctx.client.qualityReport(job),v=>{if(pin===revision.current)setResult(v);});}}>보고서 조회</button>{result!==undefined&&<Json value={result}/>}
 </section>;
}
