import { useState } from 'react';
import { api } from '../api.js';
import ForgettingCurve from '../components/ForgettingCurve.jsx';

// 复习页（#5 功能2）：FSRS 间隔重复演示 + 遗忘曲线。
const RATINGS = [
  { v: 1, label: '忘了', color: '#e5484d' },
  { v: 2, label: '困难', color: '#f0a020' },
  { v: 3, label: '良好', color: '#5b8cff' },
  { v: 4, label: '容易', color: '#38c79a' },
];

export default function ReviewPage() {
  const [card, setCard] = useState(null);
  const [history, setHistory] = useState([]);
  const [err, setErr] = useState(null);

  const rate = async (rating) => {
    setErr(null);
    try {
      const res = await api.reviewSchedule(rating, card || undefined);
      setCard(res.card);
      setHistory((h) => [{ rating, interval: res.interval_days,
        stability: res.card.stability, ts: Date.now() }, ...h].slice(0, 12));
    } catch (e) { setErr(e.message); }
  };

  return (
    <div>
      <h1 className="page-title">复习</h1>
      <p className="page-sub">FSRS-5 间隔重复 · 遗忘曲线</p>

      <div className="grid cols-2" style={{ alignItems: 'start' }}>
        <div className="card">
          <h3>间隔重复演示</h3>
          <p className="muted" style={{ marginBottom: 14 }}>
            对一张卡评分，看 FSRS 如何排下次复习。
            {card ? ` 当前：稳定性 ${card.stability?.toFixed(1)} · 复习 ${card.reps} 次` : ' 当前：新卡'}
          </p>
          <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
            {RATINGS.map((r) => (
              <button key={r.v} style={{ background: r.color }} onClick={() => rate(r.v)}>{r.label}</button>
            ))}
            {card && <button className="ghost" onClick={() => { setCard(null); setHistory([]); }}>重置</button>}
          </div>
          {err && <p className="tag bad" style={{ marginTop: 12 }}>{err}</p>}
          <div className="feed" style={{ marginTop: 16 }}>
            {history.length === 0 && <div className="empty">还没评分</div>}
            {history.map((h, i) => (
              <div className="feed-item" key={i}>
                <span>{RATINGS.find((r) => r.v === h.rating)?.label}</span>
                <span className="muted">下次 {h.interval} 天后 · S={h.stability?.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>遗忘曲线（FSRS 保持率模型）</h3>
            <ForgettingCurve />
          </div>
        </div>
      </div>
    </div>
  );
}
