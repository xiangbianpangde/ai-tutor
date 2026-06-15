// 遗忘曲线（#5 功能2）：客户端按 FSRS-5 保持率公式 R=(1+FACTOR·t/S)^DECAY 画曲线。
// 与后端 backend/strategy/fsrs.py 同一公式，不同 stability 一条线，直观展示间隔效应。
const W = 680;
const H = 280;
const PAD = 40;
const DECAY = -0.5;
const FACTOR = 19 / 81;
const DAYS = 30;
const STABILITIES = [
  { s: 2, color: '#e5484d', label: 'S=2（新学）' },
  { s: 7, color: '#f0a020', label: 'S=7（复习1次）' },
  { s: 20, color: '#38c79a', label: 'S=20（巩固）' },
];

function retr(t, s) { return (1 + FACTOR * t / s) ** DECAY; }

export default function ForgettingCurve() {
  const x = (t) => PAD + (t / DAYS) * (W - 2 * PAD);
  const y = (r) => PAD + (1 - r) * (H - 2 * PAD);

  return (
    <div className="viz-wrap" style={{ padding: 14 }}>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="遗忘曲线">
        {/* 轴 */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#2a2f3a" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#2a2f3a" />
        {[0, 0.5, 0.9, 1].map((r) => (
          <g key={r}>
            <line x1={PAD} y1={y(r)} x2={W - PAD} y2={y(r)} stroke="#1e222d" strokeDasharray="3 3" />
            <text x={8} y={y(r) + 4} fontSize="10" fill="#8b90a0">{Math.round(r * 100)}%</text>
          </g>
        ))}
        {/* 0.9 目标线 */}
        <text x={W - PAD - 60} y={y(0.9) - 6} fontSize="10" fill="#38c79a">目标保持率 90%</text>
        {STABILITIES.map(({ s, color }) => {
          const pts = Array.from({ length: DAYS + 1 }, (_, t) => `${x(t)},${y(retr(t, s))}`).join(' ');
          return <polyline key={s} points={pts} fill="none" stroke={color} strokeWidth="2" />;
        })}
        <text x={W / 2 - 30} y={H - 8} fontSize="11" fill="#8b90a0">天数 →</text>
      </svg>
      <div className="legend">
        {STABILITIES.map(({ s, color, label }) => (
          <span key={s}><span className="swatch" style={{ background: color }} />{label}</span>
        ))}
      </div>
    </div>
  );
}
