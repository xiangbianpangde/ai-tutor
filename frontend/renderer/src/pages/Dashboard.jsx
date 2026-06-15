import { useEffect, useState } from 'react';
import { api } from '../api.js';

// 仪表盘：系统健康 + 缓存命中 + 实时事件流（spec 04 功能2 场景2）。
export default function Dashboard({ events, connected }) {
  const [health, setHealth] = useState(null);
  const [cache, setCache] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [h, c] = await Promise.all([api.systemHealth(), api.cacheStats()]);
        if (alive) { setHealth(h); setCache(c); setErr(null); }
      } catch (e) {
        if (alive) setErr(e.message);
      }
    };
    load();
    const t = setInterval(load, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const subs = health?.subsystems || {};
  const upCount = Object.values(subs).filter(Boolean).length;
  const total = Object.keys(subs).length || 5;

  return (
    <div>
      <h1 className="page-title">仪表盘</h1>
      <p className="page-sub">系统概览与实时活动</p>

      {err && <div className="card" style={{ borderColor: 'var(--bad)', marginBottom: 16 }}>
        后端不可达：{err}（确认后端已启动）</div>}

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <div className="card">
          <h3>子系统就绪</h3>
          <div className="stat">{upCount}/{total}</div>
          <div className="stat-sub">
            {Object.entries(subs).map(([k, v]) => (
              <span key={k} className={`tag ${v ? 'ok' : 'bad'}`} style={{ marginRight: 6 }}>{k}</span>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>缓存命中率</h3>
          <div className="stat">{cache ? `${Math.round((cache.hit_rate || 0) * 100)}%` : '—'}</div>
          <div className="stat-sub">命中 {cache?.hits ?? 0} · 节省 {cache?.saved_tokens ?? 0} tokens</div>
        </div>
        <div className="card">
          <h3>实时连接</h3>
          <div className="stat" style={{ color: connected ? 'var(--accent-2)' : 'var(--muted)' }}>
            {connected ? '在线' : '离线'}
          </div>
          <div className="stat-sub">版本 {health?.version || '—'}</div>
        </div>
      </div>

      <div className="card">
        <h3>实时事件流（WebSocket）</h3>
        <div className="feed">
          {(events || []).length === 0 && <div className="empty">暂无事件——开始学习后这里会实时滚动</div>}
          {(events || []).slice(0, 30).map((e, i) => (
            <div className="feed-item" key={i}>
              <span className="feed-type">{e.type}</span>
              <span className="muted">{e.payload && Object.keys(e.payload).length
                ? JSON.stringify(e.payload).slice(0, 60) : ''}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
