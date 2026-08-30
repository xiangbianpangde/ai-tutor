import { useEffect, useState } from 'react';
import { api } from '../api.js';
import {
  IconPulse, IconDatabase, IconInbox, IconBolt, IconBook, IconCheck, IconAlert,
  IconClock, IconGraduation,
} from '../components/Icons.jsx';
import CountUp from '../components/CountUp.jsx';
import SpotlightCard from '../components/SpotlightCard.jsx';

// 仪表盘（spec 04 功能2 场景2）：系统健康 + 缓存命中 + 最近会话 + 实时事件流。

// SVG 进度环：value 0..1
function Ring({ value, size = 54, color = 'var(--accent)', label }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value || 0));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--panel-3)" strokeWidth="6" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="6"
        strokeLinecap="round" strokeDasharray={`${c * v} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="53%" textAnchor="middle" dominantBaseline="middle"
        fontSize="12.5" fontWeight="700" fill="var(--text-strong)">
        {label ?? `${Math.round(v * 100)}%`}
      </text>
    </svg>
  );
}

// 事件类型 → 图标与色调
const EVENT_STYLE = {
  session_started: { icon: IconBolt, cls: 'info' },
  action_presented: { icon: IconBook, cls: '' },
  answer_submitted: { icon: IconCheck, cls: 'ok' },
  feedback_ready: { icon: IconCheck, cls: 'ok' },
  session_completed: { icon: IconGraduation, cls: 'ok' },
  error: { icon: IconAlert, cls: 'bad' },
};

// payload → 人话（不再 dump JSON）
function describeEvent(e) {
  const p = e.payload || {};
  const parts = [];
  if (p.subject_name || p.subject_id) parts.push(`科目 ${p.subject_name || p.subject_id}`);
  if (p.concept) parts.push(`概念「${p.concept}」`);
  if (p.correctness) parts.push(`判定 ${p.correctness}`);
  if (p.message) parts.push(p.message);
  if (parts.length === 0) {
    const rest = Object.entries(p).slice(0, 2).map(([k, v]) => `${k}=${String(v).slice(0, 18)}`);
    if (rest.length) parts.push(rest.join(' · '));
  }
  return parts.join(' · ');
}

function relTime(ts) {
  // Sanity gate: ts must be epoch milliseconds within ±24h of the renderer's
  // clock. Anything else (seconds-precision values, perf_counter leftovers,
  // undefined) renders as '—' instead of absurd "496190 小时前".
  if (!ts || typeof ts !== 'number' || ts < 1e12 || ts > Date.now() + 86_400_000) return '—';
  const d = Date.now() - ts;
  if (d < 60_000) return '刚刚';
  if (d < 3_600_000) return `${Math.floor(d / 60_000)} 分钟前`;
  return `${Math.floor(d / 3_600_000)} 小时前`;
}

export default function Dashboard({ events, connected }) {
  const [health, setHealth] = useState(null);
  const [cache, setCache] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [err, setErr] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [h, c, s] = await Promise.all([
          api.systemHealth(), api.cacheStats(),
          api.listSessions('demo-user').catch(() => []),
        ]);
        if (alive) { setHealth(h); setCache(c); setSessions(s || []); setErr(null); setUpdatedAt(Date.now()); }
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
  const hitRate = cache ? (cache.hit_rate || 0) : 0;
  const active = sessions.filter((s) => s.status === 'active').length;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">仪表盘</h1>
          <p className="page-sub">系统概览与实时活动</p>
        </div>
        <div className="page-actions">
          {updatedAt && <span className="tag"><IconClock /> {relTime(updatedAt)}刷新 · 每 5 秒自动</span>}
        </div>
      </div>

      {err && (
        <div className="banner"><IconAlert />
          <span>后端不可达：{err}。请确认后端已启动（127.0.0.1:18501）。</span>
        </div>
      )}

      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <div className="card stat-card" style={{ '--bar': 'var(--accent)' }}>
          <h3><IconPulse /> 子系统就绪</h3>
          <div className="stat">
            <CountUp to={upCount} /><span className="muted" style={{ fontSize: 18 }}>/{total}</span>
            <Ring value={total ? upCount / total : 0} label={`${upCount}/${total}`} />
          </div>
          <div className="stat-sub" style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 10 }}>
            {Object.entries(subs).map(([k, v]) => (
              <span key={k} className={`tag ${v ? 'ok' : 'bad'}`}>{k}</span>
            ))}
          </div>
        </div>

        <div className="card stat-card" style={{ '--bar': 'var(--accent-2)' }}>
          <h3><IconDatabase /> 缓存命中率</h3>
          <div className="stat">
            <Ring value={hitRate} color="var(--accent-2)" />
          </div>
          <div className="stat-sub">命中 {cache?.hits ?? 0} 次 · 节省 {cache?.saved_tokens ?? 0} tokens</div>
        </div>

        <SpotlightCard className="card stat-card" style={{ '--bar': 'var(--purple)' }}>
          <h3><IconBook /> 我的科目会话</h3>
          <div className="stat"><CountUp to={sessions.length} /></div>
          <div className="stat-sub">{active > 0 ? `${active} 个进行中` : '暂无进行中的学习'}</div>
        </SpotlightCard>

        <SpotlightCard className="card stat-card" style={{ '--bar': connected ? 'var(--accent-2)' : 'var(--faint)' }}>
          <h3><IconBolt /> 实时通道</h3>
          <div className="stat" style={{ color: connected ? 'var(--accent-2)' : 'var(--faint)', fontSize: 22 }}>
            {connected ? '在线' : '离线'}
          </div>
          <div className="stat-sub">WebSocket /ws/events · v{health?.version || '—'}</div>
        </SpotlightCard>
      </div>

      <div className="grid-main">
        <div className="card">
          <h3><IconInbox /> 实时事件流</h3>
          <div className="feed">
            {(events || []).length === 0 && (
              <div className="empty">
                <IconInbox size={34} />
                暂无事件——到「学习中心」开始一次学习，这里会实时滚动
              </div>
            )}
            {(events || []).slice(0, 30).map((e, i) => {
              const st = EVENT_STYLE[e.type] || { icon: IconPulse, cls: '' };
              const Ic = st.icon;
              return (
                <div className="feed-item" key={i}>
                  <span className={`feed-icon tag-${st.cls}`}><Ic size={14} /></span>
                  <div className="feed-body">
                    <div className="feed-type">{e.type}</div>
                    <div className="feed-desc">{describeEvent(e) || '—'}</div>
                  </div>
                  {e.ts && <span className="feed-time">{relTime(e.ts)}</span>}
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <h3><IconBook /> 最近学习</h3>
          {sessions.length === 0 && (
            <div className="empty">
              <IconBook size={34} />
              还没有学习记录——去「学习中心」开第一课
            </div>
          )}
          <div className="timeline">
            {sessions.slice(0, 8).map((s) => (
              <div className="timeline-item" key={s.session_id || s.id}>
                <span className="tl-dot" style={{ background: s.status === 'active' ? 'var(--accent-2)' : 'var(--faint)' }} />
                <span style={{ flex: 1 }}>
                  {s.subject_name || s.subject_id || '未知科目'}
                  <span className="faint mono" style={{ marginLeft: 8 }}>
                    {(s.session_id || s.id || '').slice(0, 10)}
                  </span>
                </span>
                <span className={`tag ${s.status === 'active' ? 'ok' : ''}`}>
                  {s.status === 'active' ? '进行中' : (s.status || '已结束')}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
