import { useEffect, useRef, useState, cloneElement, isValidElement, type ReactElement, type ReactNode } from 'react';
import { ApiRequestError } from './client';
export function safeError(error: unknown) {
 if(error instanceof ApiRequestError) return error.status===403?'이 작업을 실행할 권한이 없습니다.':error.status===404?'항목을 찾을 수 없거나 접근할 수 없습니다.':error.status===401?'인증이 만료되었습니다. 다시 연결해 주세요.':error.status===409?'현재 상태에서 실행할 수 없습니다. 설정과 작업 상태를 확인해 주세요.':error.status===422?'입력값과 설정을 확인해 주세요.':'서비스 요청을 완료하지 못했습니다.';
 return '서비스에 연결할 수 없습니다.';
}
export function useTask() {
 const alive=useRef(true);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 async function run<T>(fn:()=>Promise<T>, done?:(value:T)=>void) {setBusy(true);setError('');try{const value=await fn();if(alive.current)done?.(value);return value;}catch(e){if(alive.current)setError(safeError(e));}finally{if(alive.current)setBusy(false);}}
 return {busy,error,run,notice:error?<p role="alert" className="error">{error}</p>:null};
}
export function Json({value}:{value:unknown}) {return <pre className="json">{JSON.stringify(value,null,2)}</pre>;}
export function Field({label,children}:{label:string;children:ReactNode}) {return <label className="field"><span>{label}</span>{isValidElement(children)?cloneElement(children as ReactElement<{'aria-label'?:string}>,{'aria-label':label}):children}</label>;}
export function Toggle({label,checked,onChange,disabled=false}:{label:string;checked:boolean;onChange:(v:boolean)=>void;disabled?:boolean}) {return <label className="check"><input type="checkbox" checked={checked} disabled={disabled} onChange={e=>onChange(e.target.checked)}/>{label}</label>;}
export const ids=(text:string)=>[...new Set(text.split(/[\n,]/).map(s=>s.trim()).filter(Boolean))];
