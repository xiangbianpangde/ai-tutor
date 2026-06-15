// 掌握度/认知负荷热力图（#5 功能3）：概念按认知负荷着色的网格。
// 数据来自 /graphs/{kg}/view 的 load 字段（0..1，越高越红）。
const COLS = 12;

function color(v) {
  // 低负荷=绿，高负荷=红（HSL 插值）
  const hue = (1 - Math.max(0, Math.min(1, v))) * 130; // 130=绿 → 0=红
  return `hsl(${hue}, 65%, 48%)`;
}

export default function MasteryHeatmap({ nodes }) {
  if (!nodes || nodes.length === 0) {
    return <div className="empty">无概念数据</div>;
  }
  const cell = 30;
  const rows = Math.ceil(nodes.length / COLS);
  const W = COLS * cell;
  const H = rows * cell;

  return (
    <div className="viz-wrap" style={{ padding: 14 }}>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="认知负荷热力图">
        {nodes.map((n, i) => {
          const cx = (i % COLS) * cell;
          const cy = Math.floor(i / COLS) * cell;
          const v = typeof n.load === 'number' ? n.load : 0.5;
          return (
            <rect key={n.id} className="heat-cell" x={cx} y={cy} width={cell} height={cell}
              fill={color(v)} rx="3">
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
