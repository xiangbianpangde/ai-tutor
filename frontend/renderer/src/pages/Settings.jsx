import { useState, useEffect } from 'react';
import { api } from '../api.js';

// 设置：LLM provider/key（存 localStorage）+ 学习偏好 + 后端信息（spec 04 功能2 场景3）。
const KEY = 'aitutor.settings';

export default function Settings() {
  const [s, setS] = useState({ provider: 'deepseek', apiKey: '', dailyGoalMin: 45, pomodoroMin: 25 });
  const [saved, setSaved] = useState(false);
  const [backend, setBackend] = useState(null);

  useEffect(() => {
    const raw = localStorage.getItem(KEY);
    if (raw) { try { setS({ ...s, ...JSON.parse(raw) }); } catch { /* ignore */ } }
    api.systemHealth().then(setBackend).catch(() => setBackend(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = () => {
    localStorage.setItem(KEY, JSON.stringify(s));
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  };

  return (
    <div>
      <h1 className="page-title">设置</h1>
      <p className="page-sub">LLM 配置与学习偏好（保存在本地）</p>

      <div className="grid cols-2">
        <div className="card">
          <h3>LLM 配置</h3>
          <label>Provider</label>
          <select value={s.provider} onChange={(e) => setS({ ...s, provider: e.target.value })}>
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama（本地）</option>
            <option value="none">暂不配置（仅基础功能）</option>
          </select>
          <label>API Key</label>
          <input type="password" value={s.apiKey} placeholder="sk-…"
            onChange={(e) => setS({ ...s, apiKey: e.target.value })} />
          <label>每日目标（分钟）</label>
          <input type="number" value={s.dailyGoalMin}
            onChange={(e) => setS({ ...s, dailyGoalMin: Number(e.target.value) })} />
          <label>番茄钟（分钟）</label>
          <input type="number" value={s.pomodoroMin}
            onChange={(e) => setS({ ...s, pomodoroMin: Number(e.target.value) })} />
          <div style={{ marginTop: 18 }} className="row">
            <button onClick={save}>保存设置</button>
            {saved && <span className="tag ok">已保存 ✓</span>}
          </div>
        </div>

        <div className="card">
          <h3>后端信息</h3>
          <p className="muted">基址：{api.base}</p>
          <p className="muted">版本：{backend?.version || '不可达'}</p>
          <div className="stat-sub" style={{ marginTop: 10 }}>
            {backend?.subsystems && Object.entries(backend.subsystems).map(([k, v]) => (
              <span key={k} className={`tag ${v ? 'ok' : 'bad'}`} style={{ marginRight: 6 }}>{k}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
