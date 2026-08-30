import { useState, useEffect } from 'react';
import { api } from '../api.js';
import ForceGraph from '../components/ForceGraph.jsx';
import MasteryHeatmap from '../components/MasteryHeatmap.jsx';
import {
  IconGraph, IconSearch, IconAlert, IconSpark, IconBook, IconBrain,
} from '../components/Icons.jsx';

// 知识图谱页（#5 功能1+3）：选科目 → 力导向图 + 认知负荷热力图 + 节点详情 + RAG 资料问答。
const USER_KEY = 'aitutor.user';
function currentUser() {
  return localStorage.getItem(USER_KEY) || 'demo-user';
}

export default function KnowledgeGraph() {
  const [subjects, setSubjects] = useState([]);
  const [userId, setUserId] = useState(currentUser());
  const [picked, setPicked] = useState(null); // {subject_id, kg_id?, display_name}
  const [kgId, setKgId] = useState('');
  const [graph, setGraph] = useState(null);
  const [selected, setSelected] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  // RAG 深挖
  const [q, setQ] = useState('');
  const [ragBusy, setRagBusy] = useState(false);
  const [ragHits, setRagHits] = useState(null);
  const [ragMeta, setRagMeta] = useState(null);
  const [ragErr, setRagErr] = useState(null);
  // 答案-引用一致性验证
  const [candidate, setCandidate] = useState('');
  const [validating, setValidating] = useState(false);
  const [verdict, setVerdict] = useState(null);

  useEffect(() => {
    api.listSubjects(userId).then(setSubjects).catch(() => setSubjects([]));
  }, [userId]);

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
    setRagErr(null); setRagBusy(true); setVerdict(null);
    try {
      const res = await api.ragQuery(kgId.trim(), q.trim(), 5);
      // 真实契约：data = { chunks, confirmed, rounds, top_score, state }
      setRagHits(res?.chunks || []);
      setRagMeta({ rounds: res?.rounds, confirmed: res?.confirmed,
        topScore: res?.top_score });
    } catch (e) { setRagErr(String(e.message || e)); setRagHits(null); } finally { setRagBusy(false); }
  };

  const validate = async () => {
    const sources = (ragHits || []).map((h) => `${h.metadata?.name || h.source}: ${h.text}`)
      .slice(0, 3);
    if (!candidate.trim() || sources.length === 0) return;
    setValidating(true); setVerdict(null);
    try {
      // 无 llm_judge 时后端回退启发式（永不过度授信）
      setVerdict(await api.ragValidate(candidate.trim(), sources));
    } catch (e) { setRagErr(String(e.message || e)); } finally { setValidating(false); }
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

          {/* RAG 深挖：检索 + 元数据披露 + 答案-引用一致性验证 */}
          <div className="card" style={{ marginTop: 16 }}>
            <h3><IconSpark /> 向资料提问（RAG 深挖）</h3>
            <div className="row">
              <input value={q} placeholder="如：这个图谱里「先修关系」最密集的概念是？"
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && ask()} />
              <button onClick={ask} disabled={ragBusy || !q.trim() || !kgId.trim()}>
                {ragBusy ? <><span className="spinner" /> 检索中…</> : '提问'}
              </button>
            </div>
            {ragErr && <div className="banner" style={{ marginTop: 14, marginBottom: 0 }}><IconAlert /><span>{ragErr}</span></div>}
            {ragMeta && (
              <p className="muted" style={{ margin: '10px 0 0', fontSize: 12 }}>
                检索 {ragMeta.rounds} 轮 ·{ragMeta.confirmed ? ' 已确认' : ' 未确认（不假装）'}
                {typeof ragMeta.topScore === 'number' && ` · 最高分 ${(ragMeta.topScore * 100).toFixed(1)}%`}
              </p>
            )}
            {ragHits && (
              <div className="feed" style={{ marginTop: 14 }}>
                {ragHits.length === 0 && <div className="empty">没有检索到相关片段</div>}
                {ragHits.map((h, i) => (
                  <div className="feed-item" key={i}>
                    <span className="feed-icon"><IconBook size={14} /></span>
                    <div className="feed-body">
                      <div className="feed-type">{h.metadata?.name || h.source || h.id || `片段 ${i + 1}`}</div>
                      <div className="feed-desc" style={{ whiteSpace: 'normal' }}>
                        {String(h.text || h.content || '').slice(0, 200)}
                      </div>
                    </div>
                    {typeof h.score === 'number' && <span className="tag info">{(h.score * 100).toFixed(0)}%</span>}
                  </div>
                ))}
              </div>
            )}

            {ragHits && ragHits.length > 0 && (
              <>
                <div style={{ marginTop: 14 }}>
                  <label>答案（用于引用验证，选已验证答案可防幻觉）</label>
                  <div className="row">
                    <textarea value={candidate} rows={2}
                      placeholder="输入你的答案，验证它是否被上述片段支撑…"
                      onChange={(e) => setCandidate(e.target.value)} />
                    <button onClick={validate} disabled={validating || !candidate.trim()}>
                      {validating ? <><span className="spinner" /> 验证中…</> : '验证引用'}
                    </button>
                  </div>
                </div>
                {verdict && (
                  <div className="banner" style={{ marginTop: 14, marginBottom: 0 }}
                    data-ok={verdict.is_supported}>
                    <IconAlert />
                    <span>
                      {verdict.is_supported
                        ? `引用被支撑（信度 ${(verdict.confidence * 100).toFixed(0)}%）`
                        : `未被引用支撑（信度 ${(verdict.confidence * 100).toFixed(0)}%）：${(verdict.mismatched_claims || []).join('；') || '无引用源'}`}
                      {' · '}方式 {verdict.method}
                    </span>
                  </div>
                )}
              </>
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
