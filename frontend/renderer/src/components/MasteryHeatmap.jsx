// 掌握度/认知负荷热力图（#5 功能3）：概念按认知负荷着色的网格。
// 数据来自 /graphs/{kg}/view 的 load 字段（0..1，越高越红）。
const COLS = 12;

function color(v) {
  // 低负荷=苔绿(130)，高负荷=暖赤红(0)
  const hue = (1 - Math.max(0, Math.min(1, v))) * 130;
  return `hsl(${hue}, 65%, 48%)`;
}

export default function MasteryHeatmap({ nodes }) {
  if (!nodes || nodes.length === 0) {
    return <div className="empty" style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>无概念数据</div>;
  }
  const cell = 32;
  const rows = Math.ceil(nodes.length / COLS);
  const W = COLS * cell;
  const H = rows * cell;

  return (
    <div className="viz-wrap" style={{ padding: 16 }}>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="认知负荷热力图">
        {nodes.map((n, i) => {
          const cx = (i % COLS) * cell;
          const cy = Math.floor(i / COLS) * cell;
          const v = typeof n.load === 'number' ? n.load : 0.5;
          return (
            <rect
              key={n.id}
              className="heat-cell"
              x={cx + 2}
              y={cy + 2}
              width={cell - 4}
              height={cell - 4}
              fill={color(v)}
              rx="4"
              stroke="#ffffff"
              strokeWidth="1"
              style={{
                cursor: 'pointer',
                transition: 'transform 0.15s ease, filter 0.15s ease',
              }}
            >
              <title>{n.name}：负荷 {v.toFixed(2)}</title>
            </rect>
          );
        })}
      </svg>
      <div className="legend">
        <span><span className="swatch" style={{ background: color(0.1) }} />低负荷</span>
        <span><span className="swatch" style={{ background: color(0.5) }} />中</span>
        <span><span className="swatch" style={{ background: color(0.9) }} />高负荷</span>
        <span className="muted">· 共 {nodes.length} 概念</span>
      </div>
    </div>
  );
}
