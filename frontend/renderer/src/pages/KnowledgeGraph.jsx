import { useState, useEffect } from 'react';
import { api } from '../api.js';
import ForceGraph from '../components/ForceGraph.jsx';
import MasteryHeatmap from '../components/MasteryHeatmap.jsx';
import {
  IconGraph, IconSearch, IconAlert, IconSpark, IconBook, IconBrain,
} from '../components/Icons.jsx';

// 知识图谱页（#5 功能1+3）：选科目 → 力导向图 + 认知负荷热力图 + 节点详情 + RAG 资料问答。
export default function KnowledgeGraph() {
  const [subjects, setSubjects] = useState([]);
  const [picked, setPicked] = useState(null); // {subject_id, kg_id?, display_name}
  const [kgId, setKgId] = useState('');
  const [graph, setGraph] = useState(null);
  const [selected, setSelected] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  // RAG 问答
  const [q, setQ] = useState('');
  const [ragBusy, setRagBusy] = useState(false);
  const [ragHits, setRagHits] = useState(null);
  const [ragErr, setRagErr] = useState(null);

  useEffect(() => {
    api.listSubjects('demo-user').then(setSubjects).catch(() => setSubjects([]));
  }, []);

  const loadGraph = async (id) => {
    const target = (id || kgId).trim();
    if (!target) return;
    setErr(null); setBusy(true); setSelected(null); setRagHits(null); setRagErr(null);
    try {
      setGraph(await api.get(`/api/knowledge/graphs/${encodeURIComponent(target)}/view`));
    } catch (e) { setErr(e.message); setGraph(null); } finally { setBusy(false); }
  };

  const pickSubject = (s) => {
    setPicked(s);
    if (s.kg_id) { setKgId(s.kg_id); loadGraph(s.kg_id); }
    else setErr('该科目还没有关联的知识图谱，请先在学习中心完成一次导入建图。');
  };

  const ask = async () => {
    if (!q.trim() || !kgId.trim()) return;
    setRagErr(null); setRagBusy(true);
    try {
      const res = await api.ragQuery(kgId.trim(), q.trim(), 5);
      setRagHits(res?.hits || res?.results || res || []);
    } catch (e) { setRagErr(e.message); setRagHits(null); } finally { setRagBusy(false); }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">知识图谱</h1>
          <p className="page-sub">力导向图 · 认知负荷热力图 · 资料问答</p>
        </div>
      </div>

      {/* 选科入口（免手填 KG ID） */}
      {subjects.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3><IconBook /> 从我的科目浏览</h3>
          <div className="subject-grid">
            {subjects.map((s) => (
              <button key={s.subject_id}
                className={`subject-card${picked?.subject_id === s.subject_id ? ' selected' : ''}`}
                onClick={() => pickSubject(s)}>
                <div className="sc-name">{s.display_name}</div>
                <div className="sc-meta"><span className="tag info">{s.concepts} 概念</span></div>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="row" style={{ marginBottom: 18, maxWidth: 560 }}>
        <input value={kgId} placeholder="或直接输入 KG ID（如 kg-xxxx）"
          onChange={(e) => setKgId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && loadGraph()} />
        <button onClick={() => loadGraph()} disabled={busy || !kgId.trim()}>
          {busy ? <><span className="spinner" /> 加载中…</> : <><IconSearch /> 加载</>}
        </button>
      </div>
      {err && <div className="banner"><IconAlert /><span>{err}</span></div>}

      {graph && (
        <>
          <p className="muted" style={{ marginBottom: 12, marginTop: 0 }}>
            共 <strong style={{ color: 'var(--text-strong)' }}>{graph.node_count}</strong> 概念 ·
            <strong style={{ color: 'var(--text-strong)' }}> {graph.edge_count}</strong> 条关系
          </p>
          <div className="grid-main" style={{ gridTemplateColumns: '3fr 2fr' }}>
            <ForceGraph nodes={graph.nodes} edges={graph.edges} onSelect={setSelected} />
            <div>
              <MasteryHeatmap nodes={graph.nodes} />
              {selected && (
                <div className="card" style={{ marginTop: 16, animation: 'fadeUp 0.2s' }}>
                  <h3><IconBrain /> 概念详情</h3>
                  <div className="card-title-serif" style={{ marginBottom: 8 }}>{selected.name}</div>
                  <p style={{ margin: '0 0 10px' }}><span className="tag info">{selected.category}</span></p>
                  <div className="kv"><span className="k">抽象度</span><span className="v">{selected.abstract_level?.toFixed(2)}</span></div>
                  <div className="kv"><span className="k">认知负荷</span><span className="v">{selected.load?.toFixed(2)}</span></div>
                </div>
              )}
            </div>
          </div>

          {/* RAG 资料问答 */}
          <div className="card" style={{ marginTop: 16 }}>
            <h3><IconSpark /> 向资料提问（RAG）</h3>
            <div className="row">
              <input value={q} placeholder="如：这个图谱里「先修关系」最密集的概念是？"
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && ask()} />
              <button onClick={ask} disabled={ragBusy || !q.trim() || !kgId.trim()}>
                {ragBusy ? <><span className="spinner" /> 检索中…</> : '提问'}
              </button>
            </div>
            {ragErr && <div className="banner" style={{ marginTop: 14, marginBottom: 0 }}><IconAlert /><span>{ragErr}</span></div>}
            {ragHits && (
              <div className="feed" style={{ marginTop: 14 }}>
                {ragHits.length === 0 && <div className="empty">没有检索到相关片段</div>}
                {ragHits.map((h, i) => (
                  <div className="feed-item" key={i}>
                    <span className="feed-icon"><IconBook size={14} /></span>
                    <div className="feed-body">
                      <div className="feed-type">{h.concept || h.title || h.id || `片段 ${i + 1}`}</div>
                      <div className="feed-desc" style={{ whiteSpace: 'normal' }}>
                        {String(h.text || h.content || h.summary || '').slice(0, 160)}
                      </div>
                    </div>
                    {typeof h.score === 'number' && <span className="tag info">{(h.score * 100).toFixed(0)}%</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
      {!graph && !err && (
        <div className="empty">
          <IconGraph size={36} />
          点上面一个科目，或输入 KG ID 开始浏览
        </div>
      )}
    </div>
  );
}
