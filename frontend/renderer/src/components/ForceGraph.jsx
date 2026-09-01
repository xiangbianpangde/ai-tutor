import { useEffect, useRef, useState } from 'react';
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force';

// KG 力导向图（#5 功能1）：Claude 暖纸风格可视化
const CAT_COLOR = {
  definition: '#d97757', // 赤陶橘
  theorem: '#5f9268',    // 苔绿
  method: '#bd832e',     // 暖琥珀
  example: '#8f76c4',    // 柔紫
  property: '#c25d7d',   // 玫红
  default: '#aaa89d',    // 暖灰
};
const W = 720;
const H = 480;

export default function ForceGraph({ nodes, edges, onSelect }) {
  const [positioned, setPositioned] = useState([]);
  const [links, setLinks] = useState([]);
  const [hover, setHover] = useState(null);
  const simRef = useRef(null);

  useEffect(() => {
    if (!nodes || nodes.length === 0) { setPositioned([]); setLinks([]); return; }
    // 复制（d3 会突变对象）
    const ns = nodes.map((n) => ({ ...n }));
    const es = edges.map((e) => ({ source: e.from, target: e.to, type: e.type }));
    const sim = forceSimulation(ns)
      .force('link', forceLink(es).id((d) => d.id).distance(75).strength(0.4))
      .force('charge', forceManyBody().strength(-220))
      .force('center', forceCenter(W / 2, H / 2))
      .force('collide', forceCollide(22))
      .stop();
    // 同步跑若干 tick（确定性布局）
    for (let i = 0; i < 220; i++) sim.tick();
    ns.forEach((n) => {
      n.x = Math.max(24, Math.min(W - 24, n.x));
      n.y = Math.max(24, Math.min(H - 24, n.y));
    });
    setPositioned(ns);
    setLinks(es.map((e) => ({
      x1: e.source.x, y1: e.source.y, x2: e.target.x, y2: e.target.y, type: e.type,
    })));
    simRef.current = sim;
    return () => sim.stop();
  }, [nodes, edges]);

  if (!nodes || nodes.length === 0) {
    return <div className="empty" style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>无图数据——先在「学习中心」选个已建图的科目，或输入 KG ID</div>;
  }

  return (
    <div className="viz-wrap">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="知识图谱">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#c7c3b4" />
          </marker>
        </defs>

        {links.map((l, i) => (
          <line
            key={i}
            x1={l.x1}
            y1={l.y1}
            x2={l.x2}
            y2={l.y2}
            stroke={l.type === 'prerequisite_strong' ? '#d97757' : '#ddd9cc'}
            strokeWidth={l.type === 'prerequisite_strong' ? 2 : 1}
            strokeDasharray={l.type === 'prerequisite_strong' ? 'none' : '3 3'}
            markerEnd="url(#arrow)"
          />
        ))}

        {positioned.map((n) => {
          const col = CAT_COLOR[n.category] || CAT_COLOR.default;
          const isH = hover === n.id;
          return (
            <g
              key={n.id}
              transform={`translate(${n.x},${n.y})`}
              style={{ cursor: 'pointer' }}
              onClick={() => onSelect && onSelect(n)}
              onMouseEnter={() => setHover(n.id)}
              onMouseLeave={() => setHover(null)}
            >
              <circle
                r={isH ? 13 : 9.5}
                fill={col}
                stroke="#ffffff"
                strokeWidth="2.5"
                style={{
                  filter: isH ? 'drop-shadow(0 2px 8px rgba(74, 62, 38, 0.25))' : 'drop-shadow(0 1px 3px rgba(74, 62, 38, 0.15))',
                  transition: 'all 0.2s ease',
                }}
              />
              <text
                x="14"
                y="4.5"
                fontSize="11.5"
                fontWeight="500"
                fill="#3d3929"
              >
                {n.name}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="legend">
        {Object.entries(CAT_COLOR).filter(([k]) => k !== 'default').map(([k, c]) => (
          <span key={k}>
            <span className="swatch" style={{ background: c }} />
            {k}
          </span>
        ))}
      </div>
    </div>
  );
}
