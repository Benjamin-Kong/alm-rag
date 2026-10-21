// SRS-033/034/058: real quality job submission, no synthetic metric claims.
import { afterEach,expect,test,vi } from 'vitest';
import { cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { Evaluation } from './Evaluation';
import type { ConsoleContext } from './App';
afterEach(cleanup);
function context(manage=true){return {principal:{admin_session:false,project_uids:['p'],permissions:manage?['project_read','project_manage']:['project_read']},projects:[{project_uid:'p',name:'P',source_project_id:'P',alm_instance_uid:'s'}],client:{stageEvaluation:vi.fn(async()=>({dataset_ref:'d',case_count:1})),evaluate:vi.fn(async()=>({job_id:'e'})),integrity:vi.fn(async()=>({job_id:'i'})),qualityReport:vi.fn(async()=>({job_id:'e',project_uid:'p',status:'PASS',report:{precision_at_k:0.5}}))},refresh:vi.fn()} as unknown as ConsoleContext;}
test('quality UI stages project-bound gold data and retrieves actual server report',async()=>{
 const ctx=context();render(<Evaluation ctx={ctx}/>);
 fireEvent.change(screen.getByLabelText('평가 검색어'),{target:{value:'brake'}});
 fireEvent.change(screen.getByLabelText('정답 Item UID (한 줄에 하나)'),{target:{value:'item'}});
 fireEvent.click(screen.getByRole('button',{name:'골든셋 저장'}));
 await waitFor(()=>expect(ctx.client.stageEvaluation).toHaveBeenCalledWith('p',{cases:[{query:'brake',relevant_item_uids:['item']}]}));
 fireEvent.click(screen.getByRole('button',{name:'세 검색 방식 평가'}));
 await waitFor(()=>expect(ctx.client.evaluate).toHaveBeenCalledWith('p','d',10));
 fireEvent.click(screen.getByRole('button',{name:'보고서 조회'}));
 await screen.findByText(/precision_at_k/);
 expect(ctx.client.qualityReport).toHaveBeenCalledWith('e');
});
test('read-only role cannot submit quality jobs',()=>{
 render(<Evaluation ctx={context(false)}/>);
 expect((screen.getByRole('button',{name:'무결성 검사'}) as HTMLButtonElement).disabled).toBe(true);
 expect((screen.getByRole('button',{name:'골든셋 저장'}) as HTMLButtonElement).disabled).toBe(true);
});
test('late dataset response cannot restore readiness after query changes',async()=>{
 let finish!:(v:unknown)=>void;const ctx=context();
 ctx.client.stageEvaluation=vi.fn(()=>new Promise(resolve=>{finish=resolve;})) as typeof ctx.client.stageEvaluation;
 render(<Evaluation ctx={ctx}/>);
 fireEvent.change(screen.getByLabelText('평가 검색어'),{target:{value:'old'}});
 fireEvent.change(screen.getByLabelText('정답 Item UID (한 줄에 하나)'),{target:{value:'item'}});
 fireEvent.click(screen.getByRole('button',{name:'골든셋 저장'}));
 fireEvent.change(screen.getByLabelText('평가 검색어'),{target:{value:'new'}});
 finish({dataset_ref:'old-data',project_uid:'p',case_count:1,sha256:'a'.repeat(64)});
 await waitFor(()=>expect((screen.getByRole('button',{name:'골든셋 저장'}) as HTMLButtonElement).disabled).toBe(false));
 expect((screen.getByRole('button',{name:'세 검색 방식 평가'}) as HTMLButtonElement).disabled).toBe(true);
});
