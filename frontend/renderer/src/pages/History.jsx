import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { IconHistory, IconSpark } from '../components/Icons.jsx';

// 会话历史回放（清单第 6 项）：跨会话判分详情时间线 + 概览，复盘"我之前怎么错的"。
// 数据来自后端真实持久化（sessions.context_json.recent_history）。
const USER_KEY = 'aitutor.user';
function currentUser() {
  return localStorage.getItem(USER_KEY) || 'demo-user';
}

const CORRECTNESS = {
  correct: { label: '正确', cls: 'ok' },
  partial: { label: '部分', cls: 'warn' },
  incorrect: { label: '错误', cls: 'bad' },
};

function fmtTs(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts.slice(0, 16) || '—';
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export default function History() {
  const [userId, setUserId] = useState(currentUser());
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = (uid) => {
    setLoading(true); setErr(null);
    api.get(`/api/tutoring/users/${encodeURIComponent(uid)}/session-history`)
      .then(setData)
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(userId); }, [userId]);

  const ov = data?.overview;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">会话历史</h1>
          <p className="page-sub">跨会话判分回放 · 复盘之前怎么错的</p>
        </div>
      </div>

      <div className="row" style={{ gap: 10, marginBottom: 16, alignItems: 'end' }}>
        <div>
          <label>用户 ID</label>
          <input type="text" value={userId} style={{ width: 180 }}
            onChange={(e) => setUserId(e.target.value)} />
        </div>
      </div>

      {err && <div className="banner error"><span>{err}</span></div>}
      {loading && <div className="card"><span className="muted">加载中…</span></div>}

      {!loading && !err && ov && (
        <>
          <div className="grid cols-4" style={{ marginBottom: 16 }}>
            <div className="card diag-stat">
              <span className="num">{ov.sessions}</span><span className="stat-label">会话</span>
            </div>
            <div className="card diag-stat">
              <span className="num">{ov.attempts}</span><span className="stat-label">判分次数</span>
            </div>
            <div className="card diag-stat">
              <span className="num ok-text">{ov.correct}</span><span className="stat-label">正确</span>
            </div>
            <div className="card diag-stat">
              <span className="num">{Math.round((ov.correct_rate || 0) * 100)}%</span>
              <span className="stat-label">正确率</span>
            </div>
          </div>

          <div className="card">
            <h3><IconHistory /> 回放时间线（最新在前）</h3>
            {data.entries.length === 0 && (
              <p className="muted">还没有判分记录——去「学习中心」开始一次学习。</p>
            )}
            <div className="timeline">
              {data.entries.map((e, i) => {
                const meta = CORRECTNESS[e.correctness] || { label: e.correctness || '—', cls: '' };
                return (
                  <div className="timeline-item" key={i} style={{ alignItems: 'flex-start' }}>
                    <span className={`tl-dot ${e.correctness === 'correct' ? 'ok' : ''}`}
                      style={{ background: e.correctness === 'correct' ? 'var(--accent-2)' : e.correctness === 'partial' ? 'var(--warn)' : 'var(--bad)' }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                        <strong>{e.concept_name}</strong>
                        <span className={`tag ${meta.cls}`}>{meta.label}</span>
                        {e.was_self_corrected && <span className="tag info">自我纠正</span>}
                        <span className="muted" style={{ fontSize: 12 }}>{fmtTs(e.timestamp)}</span>
                      </div>
                      {e.answer && (
                        <div className="muted" style={{ fontSize: 12, marginTop: 4, whiteSpace: 'normal' }}>
                          {String(e.answer).slice(0, 120)}
                          {e.answer.length > 120 ? '…' : ''}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            {data.entries.length > 0 && (
              <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
                <IconSpark /> 提示：红色/黄色条目对应「薄弱诊断」里的薄弱概念——点击诊断页可看掌握度与补救建议。
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
