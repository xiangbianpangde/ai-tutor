import { useEffect, useRef, useState } from 'react';
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force';

// KG 力导向图（#5 功能1）：d3-force 布局 → SVG 渲染。点击节点回调 onSelect。
const CAT_COLOR = {
  definition: '#d97757', theorem: '#5f9268', method: '#bd832e',
  example: '#8f76c4', property: '#c25d7d', default: '#aaa89d',
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
      .force('link', forceLink(es).id((d) => d.id).distance(70).strength(0.4))
      .force('charge', forceManyBody().strength(-220))
      .force('center', forceCenter(W / 2, H / 2))
      .force('collide', forceCollide(22))
      .stop();
    // 同步跑若干 tick（无动画，确定性布局）
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
    return <div className="empty">无图数据——先在「学习中心」选个已建图的科目，或输入 KG ID</div>;
  }

  return (
    <div className="viz-wrap">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="知识图谱">
        {links.map((l, i) => (
          <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
            stroke="#ddd9cc" strokeWidth={l.type === 'prerequisite_strong' ? 2 : 1}
            markerEnd="url(#arrow)" />
        ))}
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#c7c3b4" />
          </marker>
        </defs>
        {positioned.map((n) => (
          <g key={n.id} transform={`translate(${n.x},${n.y})`} style={{ cursor: 'pointer' }}
            onClick={() => onSelect && onSelect(n)}
            onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}>
            <circle r={hover === n.id ? 13 : 10}
              fill={CAT_COLOR[n.category] || CAT_COLOR.default}
              stroke="#ffffff" strokeWidth="2" />
            <text x="14" y="4" fontSize="11" fill="#3d3929">{n.name}</text>
          </g>
        ))}
      </svg>
      <div className="legend">
        {Object.entries(CAT_COLOR).filter(([k]) => k !== 'default').map(([k, c]) => (
          <span key={k}><span className="swatch" style={{ background: c }} />{k}</span>
        ))}
      </div>
    </div>
  );
}
