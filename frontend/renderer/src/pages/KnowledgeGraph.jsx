import { useState } from 'react';
import { api } from '../api.js';
import ForceGraph from '../components/ForceGraph.jsx';
import MasteryHeatmap from '../components/MasteryHeatmap.jsx';

// 知识图谱页（#5 功能1+3）：输入 KG ID → 力导向图 + 认知负荷热力图 + 节点详情。
export default function KnowledgeGraph() {
  const [kgId, setKgId] = useState('');
  const [graph, setGraph] = useState(null);
  const [selected, setSelected] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    if (!kgId.trim()) return;
    setErr(null); setBusy(true); setSelected(null);
    try {
      setGraph(await api.get(`/api/knowledge/graphs/${encodeURIComponent(kgId.trim())}/view`));
    } catch (e) { setErr(e.message); setGraph(null); } finally { setBusy(false); }
  };

  return (
    <div>
      <h1 className="page-title">知识图谱</h1>
      <p className="page-sub">力导向图 + 认知负荷热力图</p>

      <div className="row" style={{ marginBottom: 18, maxWidth: 520 }}>
        <input value={kgId} placeholder="输入 KG ID（如 kg-xxxx）"
          onChange={(e) => setKgId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && load()} />
        <button onClick={load} disabled={busy || !kgId.trim()}>{busy ? '加载中…' : '加载'}</button>
      </div>
      {err && <p className="tag bad" style={{ marginBottom: 14 }}>{err}</p>}

      {graph && (
        <>
          <p className="muted" style={{ marginBottom: 10 }}>
            {graph.node_count} 概念 · {graph.edge_count} 关系
          </p>
          <div className="grid cols-2" style={{ alignItems: 'start' }}>
            <ForceGraph nodes={graph.nodes} edges={graph.edges} onSelect={setSelected} />
            <div>
              <MasteryHeatmap nodes={graph.nodes} />
              {selected && (
                <div className="card" style={{ marginTop: 16 }}>
                  <h3>{selected.name}</h3>
                  <p><span className="tag">{selected.category}</span></p>
                  <p className="muted">抽象度 {selected.abstract_level?.toFixed(2)} ·
                    认知负荷 {selected.load?.toFixed(2)}</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
      {!graph && !err && <div className="empty">输入一个 KG ID 开始浏览</div>}
    </div>
  );
}
