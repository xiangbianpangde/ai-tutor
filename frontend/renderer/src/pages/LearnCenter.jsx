import { useState } from 'react';
import { api } from '../api.js';

// 学习中心：开会话 → 看教学动作 → 作答 → 实时反馈（spec 04 功能4 场景1）。
export default function LearnCenter() {
  const [form, setForm] = useState({ userId: 'demo-user', subjectId: '', kgId: '' });
  const [session, setSession] = useState(null);
  const [chat, setChat] = useState([]);
  const [answer, setAnswer] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const pushTutor = (action) => {
    if (!action) return;
    setChat((c) => [...c, { who: 'tutor', text: action.content || `[${action.type}]`, type: action.type }]);
  };

  const start = async () => {
    setErr(null); setBusy(true);
    try {
      const res = await api.startSession(form.userId, form.subjectId, form.kgId || undefined);
      setSession(res);
      setChat([]);
      pushTutor(res.current_action);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const submit = async () => {
    if (!answer.trim() || !session) return;
    const a = answer.trim();
    setChat((c) => [...c, { who: 'user', text: a }]);
    setAnswer(''); setBusy(true);
    try {
      const out = await api.respond(session.session_id, a);
      const r = out.result || {};
      const fb = `${r.feedback || ''}${r.correctness ? `\n（判定：${r.correctness}）` : ''}`;
      setChat((c) => [...c, { who: 'tutor', text: fb.trim() || '（已记录）', type: 'feedback' }]);
      if (r.next_action) pushTutor(r.next_action);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  if (!session) {
    return (
      <div>
        <h1 className="page-title">学习中心</h1>
        <p className="page-sub">开启一次学习会话</p>
        <div className="card" style={{ maxWidth: 440 }}>
          <label>用户 ID</label>
          <input value={form.userId} onChange={(e) => setForm({ ...form, userId: e.target.value })} />
          <label>科目 ID</label>
          <input value={form.subjectId} placeholder="如 fastapi-houduankaifa"
            onChange={(e) => setForm({ ...form, subjectId: e.target.value })} />
          <label>KG ID（可选，留空从科目解析）</label>
          <input value={form.kgId} onChange={(e) => setForm({ ...form, kgId: e.target.value })} />
          <div style={{ marginTop: 18 }}>
            <button onClick={start} disabled={busy || !form.subjectId}>{busy ? '开启中…' : '开始学习'}</button>
          </div>
          {err && <p className="tag bad" style={{ marginTop: 14 }}>{err}</p>}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="page-title">学习中心</h1>
      <p className="page-sub">会话 {session.session_id.slice(0, 12)}… · 共 {session.total_concepts} 概念</p>
      <div className="card">
        <div className="chat">
          {chat.map((m, i) => (
            <div key={i} className={`bubble ${m.who}`}>
              {m.type && m.who === 'tutor' && <div className="tag" style={{ marginBottom: 6 }}>{m.type}</div>}
              {m.text}
            </div>
          ))}
        </div>
        <div className="composer">
          <textarea value={answer} placeholder="输入你的回答…" onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }} />
          <button onClick={submit} disabled={busy || !answer.trim()}>提交</button>
        </div>
        {err && <p className="tag bad" style={{ marginTop: 10 }}>{err}</p>}
      </div>
    </div>
  );
}
