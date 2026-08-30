import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { IconBook, IconTarget } from '../components/Icons.jsx';

// 学习计划页（#3 P0 跨天调度视图）：按章节 Phase 分组的跨会话计划 + 实时 BKT 进度。
// 数据来自 GET users/{id}/subjects/{subject}/learning-plan（惰性建计划 + 实时掌握度）。
const USER_KEY = 'aitutor.user';

function currentUser() {
  return localStorage.getItem(USER_KEY) || 'demo-user';
}

const PHASE_STATUS = {
  done: { label: '已完成', cls: 'ok' },
  in_progress: { label: '进行中', cls: 'info' },
  pending: { label: '待开始', cls: '' },
};

export default function Plan() {
  const [userId, setUserId] = useState(currentUser());
  const [subjects, setSubjects] = useState([]);
  const [subjectId, setSubjectId] = useState('');
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);
  const [weak, setWeak] = useState([]); // 薄弱诊断：{concept_id, band, mastery}

  useEffect(() => {
    api.listSubjects(userId).then((list) => {
      setSubjects(list || []);
      if (list && list.length > 0 && !subjectId) setSubjectId(list[0].subject_id);
    }).catch((e) => setErr(String(e.message || e)));
  }, [userId]);

  useEffect(() => {
    if (!subjectId) return;
    setLoading(true); setErr(null);
    api.get(`/api/tutoring/users/${encodeURIComponent(userId)}/weak-concepts`)
      .then((d) => setWeak(d.items || []))
      .catch(() => setWeak([]));
    api.get(`/api/tutoring/users/${encodeURIComponent(userId)}/subjects/${encodeURIComponent(subjectId)}/learning-plan`)
      .then(setData)
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [userId, subjectId]);

  const progress = data?.progress;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">学习计划</h1>
          <p className="page-sub">跨会话章节计划 · 掌握度来自 BKT 实时计算</p>
        </div>
      </div>

      <div className="row" style={{ gap: 10, marginBottom: 16, alignItems: 'end' }}>
        <div>
          <label>用户</label>
          <input type="text" value={userId} style={{ width: 160 }}
            onChange={(e) => setUserId(e.target.value)} />
        </div>
        <div>
          <label>科目</label>
          <select value={subjectId} style={{ width: 200 }}
            onChange={(e) => setSubjectId(e.target.value)}>
            {subjects.length === 0 && <option value="">（无科目）</option>}
            {subjects.map((s) => (
              <option key={s.subject_id} value={s.subject_id}>{s.display_name}</option>
            ))}
          </select>
        </div>
      </div>

      {err && <div className="banner error"><span>{err}</span></div>}
      {loading && <div className="card"><span className="muted">加载中…</span></div>}

      {!loading && !err && progress && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3><IconTarget /> 总览</h3>
            <div className="row" style={{ marginTop: 6 }}>
              <span className="stat-sub">总体掌握 {Math.round((progress.overall_mastery_ratio || 0) * 100)}%</span>
              <span className="stat-sub">概念 {progress.concepts_mastered}/{progress.concepts_total}</span>
              {progress.current_phase && (
                <span className="stat-sub">当前阶段：{progress.current_phase_title}</span>
              )}
              {progress.completed && <span className="tag ok">课程已完成</span>}
              {progress.next_concept_name && (
                <span className="tag info">下一个该学：{progress.next_concept_name}</span>
              )}
            </div>
            <div style={{ background: 'var(--panel-2)', borderRadius: 5, height: 8, marginTop: 10, overflow: 'hidden' }}>
              <div style={{ width: `${Math.round((progress.overall_mastery_ratio || 0) * 100)}%`, height: '100%',
                background: 'var(--accent)', transition: 'width 300ms' }} />
            </div>
          </div>

          <div className="card">
            <h3><IconBook /> 章节阶段（{data.plan.phases.length} 个）</h3>
            {data.plan.phases.map((ph) => {
              const meta = PHASE_STATUS[ph.status] || { label: ph.status, cls: '' };
              return (
                <div key={ph.phase} style={{ padding: '10px 0', borderBottom: '1px solid var(--border-soft)' }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>{ph.title}</strong>
                    <span className={`tag ${meta.cls}`}>{meta.label}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between', marginTop: 6 }}>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {ph.concepts_mastered}/{ph.concepts_total} 已掌握 · 预计 {ph.estimated_hours} 小时
                    </span>
                    <span className="mono faint" style={{ fontSize: 12 }}>
                      {Math.round((ph.mastered_ratio || 0) * 100)}%
                    </span>
                  </div>
                  <div style={{ background: 'var(--panel-2)', borderRadius: 5, height: 6, marginTop: 4, overflow: 'hidden' }}>
                    <div style={{ width: `${Math.round((ph.mastered_ratio || 0) * 100)}%`, height: '100%',
                      background: ph.status === 'done' ? 'var(--accent-2)' : ph.status === 'in_progress' ? 'var(--accent)' : 'var(--muted)',
                      transition: 'width 300ms' }} />
                  </div>
                  <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                    薄弱点：{(() => {
                      const weakInPhase = weak.filter((w) => ph.concept_ids.includes(w.concept_id));
                      return weakInPhase.length
                        ? weakInPhase.map((w) => `${w.label} ${Math.round((w.mastery || 0) * 100)}%`).join('、')
                        : '—';
                    })()}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
