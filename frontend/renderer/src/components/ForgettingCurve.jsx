// 遗忘曲线（#5 功能2）：客户端按 FSRS-5 保持率公式 R=(1+FACTOR·t/S)^DECAY 画曲线。
// 与后端 backend/strategy/fsrs.py 同一公式，Claude 暖纸优雅风格。
const W = 680;
const H = 280;
const PAD = 40;
const DECAY = -0.5;
const FACTOR = 19 / 81;
const DAYS = 30;
const AXIS = '#e3e0d5';
const GRID = '#eeece3';
const TXT = '#87867f';

const STABILITIES = [
  { s: 2, color: '#bf4e43', label: 'S=2（新学）' },
  { s: 7, color: '#bd832e', label: 'S=7（复习1次）' },
  { s: 20, color: '#5f9268', label: 'S=20（巩固）' },
];

function retr(t, s) { return (1 + FACTOR * t / s) ** DECAY; }

export default function ForgettingCurve() {
  const x = (t) => PAD + (t / DAYS) * (W - 2 * PAD);
  const y = (r) => PAD + (1 - r) * (H - 2 * PAD);

  return (
    <div className="viz-wrap" style={{ padding: 16 }}>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="遗忘曲线">
        {/* 轴线 */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke={AXIS} strokeWidth="1.5" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke={AXIS} strokeWidth="1.5" />

        {/* 刻度网格 */}
        {[0, 0.5, 0.9, 1].map((r) => (
          <g key={r}>
            <line x1={PAD} y1={y(r)} x2={W - PAD} y2={y(r)} stroke={GRID} strokeDasharray="3 3" />
            <text x={8} y={y(r) + 4} fontSize="10.5" fill={TXT}>{Math.round(r * 100)}%</text>
          </g>
        ))}

        {/* 0.9 目标线 */}
        <line x1={PAD} y1={y(0.9)} x2={W - PAD} y2={y(0.9)} stroke="rgba(95, 146, 104, 0.5)" strokeDasharray="4 4" />
        <text x={W - PAD - 84} y={y(0.9) - 6} fontSize="11" fill="#5f9268" fontWeight="600">
          目标保持率 90%
        </text>

        {/* 曲线 */}
        {STABILITIES.map(({ s, color }) => {
          const pts = Array.from({ length: DAYS + 1 }, (_, t) => `${x(t)},${y(retr(t, s))}`).join(' ');
          return (
            <polyline
              key={s}
              points={pts}
              fill="none"
              stroke={color}
              strokeWidth="2.5"
              style={{ filter: 'drop-shadow(0 1px 2px rgba(74, 62, 38, 0.1))' }}
            />
          );
        })}

        <text x={W / 2 - 30} y={H - 8} fontSize="11" fill={TXT}>天数 →</text>
      </svg>

      <div className="legend">
        {STABILITIES.map(({ s, color, label }) => (
          <span key={s}>
            <span className="swatch" style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
