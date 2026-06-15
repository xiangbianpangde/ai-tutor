// API 封装：统一信封解包 + 错误抛出。后端基址 18501（Electron 内固定本机）。
const BASE = (typeof window !== 'undefined' && window.AITUTOR_BASE) || 'http://127.0.0.1:18501';

async function request(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`HTTP ${res.status}（响应非 JSON）`);
  }
  // 统一信封：{ok, data} 或 {ok:false, error}
  if (data && data.ok === false) {
    const msg = (data.error && (data.error.message || data.error.code)) || '请求失败';
    throw new Error(msg);
  }
  return data && 'data' in data ? data.data : data;
}

export const api = {
  base: BASE,
  get: (p) => request('GET', p),
  post: (p, body) => request('POST', p, body),

  // ── 具体端点 ──
  systemHealth: () => request('GET', '/api/meta/health'),
  cacheStats: () => request('GET', '/api/meta/cache/stats'),
  recentEvents: (limit = 50) => request('GET', `/api/meta/events?limit=${limit}`),

  listSessions: (userId) => request('GET', `/api/tutoring/sessions?user_id=${encodeURIComponent(userId)}`),
  startSession: (userId, subjectId, kgId) =>
    request('POST', '/api/tutoring/sessions/start', { user_id: userId, subject_id: subjectId, kg_id: kgId }),
  nextAction: (sid) => request('GET', `/api/tutoring/sessions/${sid}/next-action`),
  respond: (sid, answer) => request('POST', `/api/tutoring/sessions/${sid}/respond`, { answer }),
  advanceStep: (sid) => request('POST', `/api/tutoring/sessions/${sid}/advance`),

  listSubjects: (userId) => request('GET', `/api/knowledge/subjects?user_id=${encodeURIComponent(userId)}`),
  importSubject: (userId, subjectName, markdown) =>
    request('POST', '/api/knowledge/subjects/import', { user_id: userId, subject_name: subjectName, markdown }),
  getTask: (taskId) => request('GET', `/api/tasks/${taskId}`),

  ragQuery: (kgId, query, topK = 5) =>
    request('POST', '/api/knowledge/rag/query', { kg_id: kgId, query, top_k: topK }),
  reviewSchedule: (rating, card) =>
    request('POST', '/api/tutoring/review/schedule', { rating, card }),
  stageCalibrate: (scores, currentStage = 0) =>
    request('POST', '/api/tutoring/stage/calibrate', { scores, current_stage: currentStage }),
  saveFact: (userId, subjectId, content) =>
    request('POST', '/api/tutoring/memory/facts', { user_id: userId, subject_id: subjectId, content }),
  queryFacts: (userId, subjectId, q) =>
    request('GET', `/api/tutoring/memory/facts?user_id=${encodeURIComponent(userId)}&subject_id=${encodeURIComponent(subjectId)}${q ? `&query=${encodeURIComponent(q)}` : ''}`),
};

export const WS_URL = BASE.replace(/^http/, 'ws') + '/ws/events';
