import { useEffect, useState } from 'react';
import { getHealth } from './health';
import './style.css';

export function App() {
  const [state, setState] = useState<'Checking' | 'Available' | 'Unavailable'>('Checking');
  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal).then(
      () => { if (!controller.signal.aborted) setState('Available'); },
      () => { if (!controller.signal.aborted) setState('Unavailable'); },
    );
    return () => controller.abort();
  }, []);

  return <main>
    <header><span className="mark" aria-hidden="true">A</span><span>ALM WORKSPACE</span></header>
    <section className="intro"><p className="eyebrow">REQUIREMENTS · CONNECTED</p>
      <h1>ALM RAG</h1>
      <p className="description">요구사항을 연결하는 하나의 작업 공간.</p>
    </section>
    <section className="service" aria-labelledby="service-title">
      <div><p className="eyebrow">SERVICE STATUS</p><h2 id="service-title">서비스 연결</h2>
        <p>조회 서비스의 응답 상태를 확인합니다.</p></div>
      <p role="status" className={'badge '+state.toLowerCase()}><span aria-hidden="true" />{state}</p>
    </section>
    <footer>Codebeamer &amp; Polarion · Read-only workspace</footer>
  </main>;
}
