import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { IconTasks, IconClock } from '../components/Icons.jsx';

// 任务中心：#7 后台任务（导入/KG 构建）进度可视化。数据来自 GET /api/tasks。
const STATE_META = {
  running: { label: '进行中', cls: 'info' },
  succeeded: { label: '成功', cls: 'ok' },
  failed: { label: '失败', cls: 'bad' },
  pending: { label: '排队中', cls: 'warn' },
};

function fmtTime(ts) {
  // created_at 是 epoch 秒（后端 tasks 表）
  const s = Number(ts);
  if (!s || s < 1e9 || s > Date.now() / 1000 + 86400) return '—';
  const d = new Date(s * 1000);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export default function Tasks() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true); setErr(null);
    api.get('/api/tasks?limit=20')
      .then((d) => setItems(d.items || []))
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    const timer = setInterval(() => {
      if (items.some((i) => i.state === 'running' || i.state === 'pending')) load();
    }, 3000);
    return () => clearInterval(timer);
  }, [items]);

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">任务中心</h1>
          <p className="page-sub">后台任务进度（导入资料 / 知识图谱构建等）</p>
        </div>
        <button className="ghost sm" onClick={load}><IconClock /> 刷新</button>
      </div>

      {err && <div className="banner error"><span>{err}</span></div>}
      {loading && <div className="card"><span className="muted">加载中…</span></div>}
      {!loading && !err && items.length === 0 && (
        <div className="card"><p className="muted">还没有后台任务。去「学习中心」导入一份资料，任务会在这里出现。</p></div>
      )}

      {!loading && !err && items.length > 0 && (
        <div className="card">
          {items.map((item) => {
            const meta = STATE_META[item.state] || { label: item.state, cls: '' };
            const pct = Math.round((item.progress || 0) * 100);
            return (
              <div key={item.task_id} style={{ padding: '12px 0', borderBottom: '1px solid var(--border-soft)' }}>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <strong>{item.kind === 'import_subject' ? '导入资料' : item.kind}</strong>
                  <span className={`tag ${meta.cls}`}>{meta.label}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
                  <div style={{ flex: 1, background: 'var(--panel-2)', borderRadius: 5, height: 6, overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%',
                      background: item.state === 'failed' ? 'var(--bad)' : 'var(--accent)',
                      transition: 'width 300ms' }} />
                  </div>
                  <span className="mono faint" style={{ width: 40, textAlign: 'right' }}>{pct}%</span>
                </div>
                <div className="row" style={{ justifyContent: 'space-between', marginTop: 4 }}>
                  <span className="muted" style={{ fontSize: 12 }}>{item.message || item.task_id}</span>
                  <span className="faint mono" style={{ fontSize: 11 }}>{fmtTime(item.created_at)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
