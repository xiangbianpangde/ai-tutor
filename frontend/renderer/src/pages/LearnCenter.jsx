import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';
import {
  IconLearn, IconPlus, IconSend, IconArrowRight, IconAlert, IconGraduation, IconCheck,
} from '../components/Icons.jsx';

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

// 动作类型徽章色调
const ACTION_CLS = {
  explain: 'info', question: 'warn', practice: 'purple',
  feedback: 'ok', recap: '', example: 'info',
};

// 学习中心（spec 04 功能4 场景1）：选科目 → 教学对话 → 作答 → 实时反馈。
export default function LearnCenter() {
  const [form, setForm] = useState({ userId: 'demo-user', subjectId: '', kgId: '' });
  const [session, setSession] = useState(null);
  const [chat, setChat] = useState([]);
  const [answer, setAnswer] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [current, setCurrent] = useState(null); // 当前教学动作 {type, content, interactive, completed}
  const [done, setDone] = useState(false); // 本科目是否学完
  const [subjects, setSubjects] = useState([]); // 我的科目（独立验收：免手填不透明 ID）
  const [importOpen, setImportOpen] = useState(false); // 导入资料弹窗
  const [imp, setImp] = useState({ name: '', md: '', status: null });
  const chatEndRef = useRef(null);

  // 拉用户已有科目供点选
  useEffect(() => {
    if (session) return;
    api.listSubjects(form.userId).then(setSubjects).catch(() => setSubjects([]));
  }, [session, form.userId]);

  // 新消息自动滚到底部
  useEffect(() => {
    if (chatEndRef.current) chatEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [chat, busy]);

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
          setImp({ name: '', md: '', status: null });
          setImportOpen(false);
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

  const applyAction = (act, interactive, completed) => {
    if (act) {
      setChat((c) => [...c, { who: 'tutor', text: act.content || `[${act.type}]`, type: act.type }]);
    }
    setCurrent(act ? { ...act, interactive: !!interactive } : null);
    setDone(!!completed);
  };

  const start = async () => {
    setErr(null); setBusy(true);
    try {
      const res = await api.startSession(form.userId, form.subjectId, form.kgId || undefined);
      setSession(res);
      setChat([]); setDone(false);
      applyAction(res.current_action || res.action, res.interactive, res.completed);
    } catch (e) { setErr(humanize(e.message)); } finally { setBusy(false); }
  };

  // 展示步骤"继续"→ advance → 下一个动作
  const cont = async () => {
    if (!session || busy) return;
    setBusy(true);
    try {
      const out = await api.advanceStep(session.session_id);
      applyAction(out.action, out.interactive, out.completed);
    } catch (e) { setErr(humanize(e.message)); } finally { setBusy(false); }
  };

  // 问答步骤"提交"→ respond → 反馈 + 下一个动作
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
      const nxt = out.next || {};
      applyAction(nxt.action, nxt.interactive, nxt.completed);
    } catch (e) { setErr(humanize(e.message)); } finally { setBusy(false); }
  };

  /* ── 选科/开场屏 ── */
  if (!session) {
    return (
      <div>
        <div className="page-head">
          <div>
            <h1 className="page-title">学习中心</h1>
            <p className="page-sub">选一个科目，开始一次 25 分钟的专注学习</p>
          </div>
          <div className="page-actions">
            <button className="ghost" onClick={() => setImportOpen(true)}>
              <IconPlus /> 导入资料新建科目
            </button>
          </div>
        </div>

        {err && <div className="banner"><IconAlert /><span>{err}</span></div>}

        {subjects.length > 0 ? (
          <>
            <div className="nav-section" style={{ padding: '0 2px 10px' }}>我的科目 · 点击开始</div>
            <div className="subject-grid">
              {subjects.map((s) => (
                <button key={s.subject_id}
                  className={`subject-card${form.subjectId === s.subject_id ? ' selected' : ''}`}
                  onClick={() => setForm({ ...form, subjectId: s.subject_id, kgId: '' })}>
                  <div className="sc-name">{s.display_name}</div>
                  <div className="sc-meta">
                    <span className="tag info">{s.concepts} 概念</span>
                    {form.subjectId === s.subject_id && <span className="tag ok"><IconCheck /> 已选</span>}
                  </div>
                </button>
              ))}
            </div>
            <div className="row" style={{ marginTop: 22 }}>
              <button className="lg" onClick={start}
                disabled={busy || !form.subjectId}>
                {busy ? <><span className="spinner" /> 开启中…</> : <>开始学习 <IconArrowRight /></>}
              </button>
            </div>
          </>
        ) : (
          <div className="card" style={{ maxWidth: 480 }}>
            <h3><IconLearn /> 还没有科目</h3>
            <p className="muted">从导入一份带 # 标题的 Markdown 资料开始，系统会自动建知识图谱，然后就能开课。</p>
            <button onClick={() => setImportOpen(true)}><IconPlus /> 导入资料新建</button>
          </div>
        )}

        <div className="card" style={{ maxWidth: 480, marginTop: 20 }}>
          <h3>高级选项</h3>
          <label>用户 ID</label>
          <input value={form.userId} onChange={(e) => setForm({ ...form, userId: e.target.value })} />
          <label>科目 ID（手动指定，优先于上面所选）</label>
          <input value={form.subjectId} placeholder="留空则用上面点选的科目"
            onChange={(e) => setForm({ ...form, subjectId: e.target.value })} />
          <label>KG ID（可选，留空从科目解析）</label>
          <input value={form.kgId} onChange={(e) => setForm({ ...form, kgId: e.target.value })} />
        </div>

        {importOpen && (
          <div className="overlay" onClick={(e) => { if (e.target === e.currentTarget) setImportOpen(false); }}>
            <div className="modal">
              <h2><IconPlus /> 导入资料一键建科目</h2>
              <p className="muted">粘贴带 # 标题的 Markdown 资料，自动采集 + 建知识图谱，建好即可学。</p>
              <label>科目名称</label>
              <input value={imp.name} placeholder="如 线性代数入门"
                onChange={(e) => setImp({ ...imp, name: e.target.value })} />
              <label>资料内容（Markdown，用 # 标记章节）</label>
              <textarea value={imp.md} rows={9} placeholder={'# 第一章\n## 1.1 小节\n内容…'}
                style={{ resize: 'vertical', fontFamily: 'var(--mono)', fontSize: 13 }}
                onChange={(e) => setImp({ ...imp, md: e.target.value })} />
              <div style={{ marginTop: 20 }} className="row">
                <button onClick={importSubject}
                  disabled={!!imp.status || !imp.name.trim() || !imp.md.trim()}>
                  {imp.status ? <><span className="spinner" /> {imp.status}</> : '创建科目'}
                </button>
                <button className="ghost" onClick={() => setImportOpen(false)}>取消</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  /* ── 会话屏 ── */
  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">学习中心</h1>
          <p className="page-sub">
            会话 <span className="mono">{session.session_id.slice(0, 12)}…</span>
            {' '}· 共 {session.total_concepts} 概念
          </p>
        </div>
        <div className="page-actions">
          <button className="ghost sm" onClick={() => { setSession(null); setCurrent(null); setDone(false); setChat([]); }}>
            结束本次学习
          </button>
        </div>
      </div>

      <div className="card">
        <div className="chat chat-scroll">
          {chat.map((m, i) => (
            <div key={i} className={`bubble ${m.who}`}>
              {m.type && m.who === 'tutor' && (
                <div><span className={`action-badge tag-${ACTION_CLS[m.type] || ''}`}>{m.type}</span></div>
              )}
              {m.text}
            </div>
          ))}
          {busy && (
            <div className="bubble tutor typing"><span /><span /><span /></div>
          )}
          <div ref={chatEndRef} />
        </div>

        {done ? (
          <div className="row" style={{ justifyContent: 'center', padding: '12px 0', gap: 14 }}>
            <span className="tag ok" style={{ fontSize: 14, padding: '6px 14px' }}>
              <IconGraduation /> 本科目已学完
            </span>
            <button className="ghost" onClick={() => { setSession(null); setCurrent(null); setDone(false); setChat([]); }}>
              学下一科
            </button>
          </div>
        ) : current && current.interactive ? (
          <div className="composer">
            <textarea value={answer} placeholder="输入你的回答…（Enter 发送，Shift+Enter 换行）"
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }} />
            <button className="lg" onClick={submit} disabled={busy || !answer.trim()}>
              <IconSend /> 提交
            </button>
          </div>
        ) : (
          <div className="row" style={{ justifyContent: 'flex-end' }}>
            <button className="lg" onClick={cont} disabled={busy}>
              {busy ? <><span className="spinner" /> 思考中…</> : <>继续 <IconArrowRight /></>}
            </button>
          </div>
        )}
        {err && <div className="banner" style={{ marginTop: 14, marginBottom: 0 }}><IconAlert /><span>{err}</span></div>}
      </div>
    </div>
  );
}
