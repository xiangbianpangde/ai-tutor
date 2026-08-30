import { useState, useEffect } from 'react';
import { api } from '../api.js';
import ForgettingCurve from '../components/ForgettingCurve.jsx';
import { readPrefs } from './Settings.jsx';
import {
  IconFrown, IconMeh, IconSmile, IconBolt, IconReset, IconClock, IconCheck,
} from '../components/Icons.jsx';

// 复习页（#5 功能2）：今日复习队列（遗忘曲线真实到期）+ FSRS 间隔演示 + 遗忘曲线。
const RATINGS = [
  { v: 1, label: '忘了', color: '#bf4e43', icon: IconFrown },
  { v: 2, label: '困难', color: '#bd832e', icon: IconMeh },
  { v: 3, label: '良好', color: '#5b8cff', icon: IconSmile },
  { v: 4, label: '容易', color: '#5f9268', icon: IconBolt },
];

const USER_KEY = 'aitutor.user';

function currentUser() {
  return localStorage.getItem(USER_KEY) || 'demo-user';
}

export default function ReviewPage() {
  const [userId, setUserId] = useState(currentUser());
  const [due, setDue] = useState([]);
  const [dueErr, setDueErr] = useState(null);
  const [dueLoading, setDueLoading] = useState(true);
  const [card, setCard] = useState(null);
  const [history, setHistory] = useState([]);
  const [err, setErr] = useState(null);

  const loadDue = (uid) => {
    setDueErr(null);
    setDueLoading(true);
    api.get(`/api/tutoring/users/${encodeURIComponent(uid)}/review-due`)
      .then((d) => setDue(d.items || []))
      .catch((e) => setDueErr(String(e.message || e)))
      .finally(() => setDueLoading(false));
  };

  useEffect(() => { loadDue(userId); }, [userId]);

  const reportDone = async (item) => {
    try {
      await api.post(`/api/tutoring/users/${encodeURIComponent(userId)}/review/record`, {
        concept_id: item.concept_id,
        subject_id: item.subject_id,
        accuracy: 0.9,
        review_mode: 'queue',
      });
      setDue((prev) => prev.filter((x) => x.concept_id !== item.concept_id));
    } catch (e) { setDueErr(String(e.message || e)); }
  };

  const rate = async (rating) => {
    setErr(null);
    try {
      const res = await api.reviewSchedule(rating, card || undefined);
      setCard(res.card);
      setHistory((h) => [{ rating, interval: res.interval_days,
        stability: res.card.stability, ts: Date.now() }, ...h].slice(0, 12));
    } catch (e) { setErr(e.message); }
  };

  const avgInterval = history.length
    ? (history.reduce((a, h) => a + (h.interval || 0), 0) / history.length).toFixed(1)
    : null;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">复习</h1>
          <p className="page-sub">今日过期概念（遗忘曲线）· FSRS-5 间隔重复</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3><IconClock /> 今日复习队列 <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>（每日目标 {readPrefs().dailyGoalMin} 分钟）</span></h3>
        <div className="row" style={{ gap: 8, marginBottom: 8 }}>
          <span className="muted">用户</span>
          <input type="text" value={userId} style={{ width: 160 }}
            onChange={(e) => setUserId(e.target.value)} />
        </div>
        {dueErr && <div className="banner error" style={{ marginBottom: 8 }}><span>{dueErr}</span></div>}
        {dueLoading && <span className="muted">加载中…</span>}
        {!dueLoading && !dueErr && due.length === 0 && (
          <p className="muted" style={{ fontSize: 13 }}>
            今天没有到期的概念。到期项按遗忘曲线 next_review_at 计算，复习后会自动更新。
          </p>
        )}
        {due.map((item) => (
          <div key={item.concept_id} className="kv" style={{ padding: '10px 0', borderBottom: '1px solid var(--border-soft)', alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <strong>{item.label}</strong>
              <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
                逾期 {item.overdue_days} 天 · 观测 {item.n_data_points} · λ={item.lambda_param}
              </span>
            </div>
            <button className="ghost sm" style={{ marginLeft: 12 }} onClick={() => reportDone(item)}>
              <IconCheck /> 已完成
            </button>
          </div>
        ))}
      </div>

      <div className="grid-main" style={{ gridTemplateColumns: '2fr 3fr' }}>
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3><IconBolt /> 给这张卡评分</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              {card
                ? `已复习 ${card.reps} 次 · 当前稳定性 ${card.stability?.toFixed(1)}`
                : '当前是一张新卡——评一次分，看 FSRS 如何安排下次复习。'}
            </p>
            <div className="row" style={{ gap: 8 }}>
              {RATINGS.map((r) => (
                <button key={r.v} className="rate-btn" style={{ background: r.color }}
                  onClick={() => rate(r.v)}>
                  <r.icon size={20} />
                  {r.label}
                </button>
              ))}
            </div>
            {card && (
              <button className="ghost sm" style={{ marginTop: 14 }}
                onClick={() => { setCard(null); setHistory([]); }}>
                <IconReset /> 重置为新卡
              </button>
            )}
            {err && <div className="banner" style={{ marginTop: 14, marginBottom: 0 }}><span>{err}</span></div>}
          </div>

          {card && (
            <div className="card">
              <h3><IconCheck /> 卡片状态</h3>
              <div className="kv"><span className="k">稳定性 S</span><span className="v">{card.stability?.toFixed(2)}</span></div>
              <div className="kv"><span className="k">难度 D</span><span className="v">{card.difficulty?.toFixed(2) ?? '—'}</span></div>
              <div className="kv"><span className="k">复习次数</span><span className="v">{card.reps}</span></div>
              <div className="kv"><span className="k">连续正确</span><span className="v">{card.lapses !== undefined ? `${card.reps - card.lapses}` : '—'}</span></div>
            </div>
          )}
        </div>

        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3><IconClock /> 遗忘曲线（FSRS 保持率模型）</h3>
            <ForgettingCurve />
          </div>

          <div className="card">
            <h3><IconClock /> 复习历史</h3>
            {avgInterval && (
              <p className="muted" style={{ marginTop: 0 }}>近 {history.length} 次平均间隔 {avgInterval} 天</p>
            )}
            <div className="timeline">
              {history.length === 0 && <div className="empty">还没评分——点左边的评分按钮开始</div>}
              {history.map((h, i) => {
                const r = RATINGS.find((x) => x.v === h.rating);
                return (
                  <div className="timeline-item" key={i}>
                    <span className="tl-dot" style={{ background: r?.color }} />
                    <span style={{ flex: 1 }}>{r?.label}</span>
                    <span className="tag info">下次 {h.interval} 天后</span>
                    <span className="faint mono">S={h.stability?.toFixed(1)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
