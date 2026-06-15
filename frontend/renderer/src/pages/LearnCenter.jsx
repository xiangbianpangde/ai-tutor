import { useState } from 'react';
import { api } from '../api.js';

// 把后端技术错误码翻成给非技术用户看的人话（多轮点击测试 R2 发现：原始 TutorError 太技术）。
const FRIENDLY = {
  KG_QUALITY_GATE_FAILED: '资料里没找到 # 标题，建不了科目。请用 # 标记章节（如「# 第一章」「## 小节」）后再试。',
  IMPORT_EMPTY: '资料内容是空的，请先粘贴一些带 # 标题的资料。',
  SUBJECT_NOT_FOUND: '没找到这个科目。换个科目 ID，或用「导入资料新建」从零创建。',
  KG_NOT_BUILT: '这个科目还没建好知识图谱。先用「导入资料新建」，或换个已建好的科目。',
  KG_NOT_FOUND: '没找到对应的知识图谱，请检查科目/KG ID。',
};

function humanize(msg) {
  const m = String(msg || '');
  for (const [code, friendly] of Object.entries(FRIENDLY)) {
    if (m.includes(code)) return friendly;
  }
  // 兜底：剥掉 "TutorError: [CODE]" 前缀，只留中文描述
  const stripped = m.replace(/^.*?\]\s*/, '').trim();
  return stripped || '出了点问题，请重试。';
}

// 学习中心：开会话 → 看教学动作 → 作答 → 实时反馈（spec 04 功能4 场景1）。
export default function LearnCenter() {
  const [form, setForm] = useState({ userId: 'demo-user', subjectId: '', kgId: '' });
  const [session, setSession] = useState(null);
  const [chat, setChat] = useState([]);
  const [answer, setAnswer] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  // 导入资料一键建科目（#21 零门槛入口）
  const [imp, setImp] = useState({ open: false, name: '', md: '', status: null });

  const importSubject = async () => {
    if (!imp.name.trim() || !imp.md.trim()) return;
    setErr(null);
    setImp((s) => ({ ...s, status: '提交中…' }));
    try {
      const { task_id } = await api.importSubject(form.userId, imp.name.trim(), imp.md);
      // 轮询任务进度
      for (;;) {
        await new Promise((r) => setTimeout(r, 800));
        const t = await api.getTask(task_id);
        if (t.state === 'succeeded') {
          setForm((f) => ({ ...f, subjectId: t.result.subject_id, kgId: '' }));
          setImp({ open: false, name: '', md: '', status: null });
          break;
        }
        if (t.state === 'failed') {
          setImp((s) => ({ ...s, status: null }));
          setErr(`建科目失败：${humanize(t.error) || '未知错误'}`);
          break;
        }
        setImp((s) => ({ ...s, status: `${t.message || '处理中'} ${Math.round((t.progress || 0) * 100)}%` }));
      }
    } catch (e) {
      setImp((s) => ({ ...s, status: null }));
      setErr(humanize(e.message));
    }
  };

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
    } catch (e) { setErr(humanize(e.message)); } finally { setBusy(false); }
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
    } catch (e) { setErr(humanize(e.message)); } finally { setBusy(false); }
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
          <div style={{ marginTop: 18 }} className="row">
            <button onClick={start} disabled={busy || !form.subjectId}>{busy ? '开启中…' : '开始学习'}</button>
            <button className="ghost" onClick={() => setImp((s) => ({ ...s, open: !s.open }))}>
              {imp.open ? '收起' : '没有科目？导入资料新建'}
            </button>
          </div>
          {err && <p className="tag bad" style={{ marginTop: 14 }}>{err}</p>}
        </div>

        {imp.open && (
          <div className="card" style={{ maxWidth: 440, marginTop: 16 }}>
            <h3>导入资料一键建科目</h3>
            <p className="muted" style={{ marginBottom: 6 }}>
              粘贴带 # 标题的 Markdown 资料，自动采集 + 建知识图谱，建好即可学。
            </p>
            <label>科目名称</label>
            <input value={imp.name} placeholder="如 线性代数入门"
              onChange={(e) => setImp({ ...imp, name: e.target.value })} />
            <label>资料内容（Markdown）</label>
            <textarea value={imp.md} rows={8} placeholder={'# 第一章\n## 小节\n内容…'}
              style={{ resize: 'vertical' }}
              onChange={(e) => setImp({ ...imp, md: e.target.value })} />
            <div style={{ marginTop: 14 }} className="row">
              <button onClick={importSubject} disabled={!!imp.status || !imp.name.trim() || !imp.md.trim()}>
                {imp.status ? '建科目中…' : '创建科目'}
              </button>
              {imp.status && <span className="tag">{imp.status}</span>}
            </div>
          </div>
        )}
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
