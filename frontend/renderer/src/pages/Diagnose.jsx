import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { IconPulse, IconGraph, IconTarget } from '../components/Icons.jsx';

// 薄弱概念诊断：聚合 BKT 掌握度 + 近期判分历史，最薄弱的排最前。
// 数据来自后端真实计算（BKT + 会话判分历史），前端只做展示，不推断掌握度。
const USER_KEY = 'aitutor.user';

const BAND_META = {
  weak: { label: '薄弱', cls: 'bad' },
  consolidating: { label: '巩固中', cls: 'warn' },
  mastered: { label: '已掌握', cls: 'ok' },
};

export function currentUser() {
  return localStorage.getItem(USER_KEY) || 'demo-user';
}

export default function Diagnose() {
  const [userId, setUserId] = useState(currentUser());
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = (uid) => {
    setLoading(true);
    setErr(null);
    api.get(`/api/tutoring/users/${encodeURIComponent(uid)}/weak-concepts`)
      .then(setData)
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(userId); }, [userId]);

  const switchUser = (uid) => {
    if (!uid.trim()) return;
    localStorage.setItem(USER_KEY, uid.trim());
    setUserId(uid.trim());
  };

  const ov = data?.overview;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">薄弱诊断</h1>
          <p className="page-sub">基于 BKT 掌握度与判分历史的真实聚合（不推断、不放水）</p>
        </div>
      </div>

      <div className="row" style={{ marginBottom: 16, alignItems: 'end' }}>
        <div>
          <label>用户 ID</label>
          <input type="text" value={userId} style={{ width: 220 }}
            onChange={(e) => setUserId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && switchUser(userId)} />
        </div>
        <button className="ghost" style={{ marginTop: 14 }} onClick={() => switchUser(userId)}>切换</button>
      </div>

      {loading && <div className="card"><span className="muted">加载中…</span></div>}
      {err && <div className="banner error">{err}</div>}

      {!loading && !err && ov && (
        <>
          <div className="grid cols-4" style={{ marginBottom: 16 }}>
            <div className="card diag-stat">
              <span className="stat-num">{ov.concepts}</span>
              <span className="stat-label">已学概念</span>
            </div>
            <div className="card diag-stat">
              <span className="stat-num bad-text">{ov.weak}</span>
              <span className="stat-label">薄弱</span>
            </div>
            <div className="card diag-stat">
              <span className="stat-num warn-text">{ov.consolidating}</span>
              <span className="stat-label">巩固中</span>
            </div>
            <div className="card diag-stat">
              <span className="stat-num ok-text">{ov.mastered}</span>
              <span className="stat-label">已掌握</span>
            </div>
          </div>

          <div className="card">
            <h3><IconTarget /> 概念列表（最薄弱在前）</h3>
            {data.items.length === 0 && (
              <p className="muted">还没有学习记录——去「学习中心」导入资料并开课。</p>
            )}
            {data.items.map((item) => {
              const meta = BAND_META[item.band];
              const pct = Math.round(item.mastery * 100);
              return (
                <div key={item.concept_id} className="kv" style={{ alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--line)' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600 }}>
                      {item.label} <span className={`tag ${meta.cls}`}>{meta.label}</span>
                    </div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {item.attempts} 次作答 · 错 {item.wrong_attempts} 次
                      {item.observations > 0 && ` · BKT 观测 ${item.observations}`}
                    </div>
                    <div style={{ background: 'var(--surface-2)', borderRadius: 4, height: 6, marginTop: 6, overflow: 'hidden' }}>
                      <div style={{
                        width: `${pct}%`, height: '100%',
                        background: item.band === 'weak' ? 'var(--bad)' : item.band === 'consolidating' ? '#d9a441' : 'var(--ok)',
                        transition: 'width 300ms',
                      }} />
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', marginLeft: 16 }}>
                    <div className="mono" style={{ fontWeight: 700 }}>{pct}%</div>
                    <div className="muted" style={{ fontSize: 11 }}>掌握度</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3><IconPulse /> 说明</h3>
            <p className="muted" style={{ fontSize: 13 }}>
              掌握度来自 BKT（贝叶斯知识追踪）模型对每次判分结果的持续更新，
              「薄弱 / 巩固中 / 已掌握」按 50% / 80% 两档划分。这里的数字是
              真实计算结果——判分严格时推进会明显变慢，这是设计而非故障。
              复习建议：优先复习薄弱项，并隔天重答一次验证保持。
            </p>
          </div>
        </>
      )}
    </div>
  );
}
