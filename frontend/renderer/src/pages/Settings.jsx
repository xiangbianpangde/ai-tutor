import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { IconSettings, IconCheck, IconPulse, IconDatabase } from '../components/Icons.jsx';

// 设置：LLM provider/key（存 localStorage）+ 学习偏好 + 后端信息（spec 04 功能2 场景3）。
const KEY = 'aitutor.settings';

export default function Settings() {
  const [s, setS] = useState({ provider: 'deepseek', apiKey: '', dailyGoalMin: 45, pomodoroMin: 25 });
  const [saved, setSaved] = useState(false);
  const [backend, setBackend] = useState(null);

  useEffect(() => {
    const raw = localStorage.getItem(KEY);
    if (raw) { try { setS((prev) => ({ ...prev, ...JSON.parse(raw) })); } catch { /* ignore */ } }
    api.systemHealth().then(setBackend).catch(() => setBackend(null));
  }, []);

  const save = () => {
    localStorage.setItem(KEY, JSON.stringify(s));
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">设置</h1>
          <p className="page-sub">LLM 配置与学习偏好（保存在本机）</p>
        </div>
      </div>

      <div className="grid cols-2" style={{ alignItems: 'start' }}>
        <div className="card">
          <h3><IconSettings /> LLM 配置</h3>
          <label>Provider</label>
          <select value={s.provider} onChange={(e) => setS({ ...s, provider: e.target.value })}>
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama（本地）</option>
            <option value="none">暂不配置（仅基础功能）</option>
          </select>
          {s.provider !== 'none' && (
            <>
              <label>API Key</label>
              <input type="password" value={s.apiKey} placeholder="sk-…"
                onChange={(e) => setS({ ...s, apiKey: e.target.value })} />
            </>
          )}
          <label>每日目标（分钟）</label>
          <input type="number" value={s.dailyGoalMin} min={5} max={480}
            onChange={(e) => setS({ ...s, dailyGoalMin: Number(e.target.value) })} />
          <label>番茄钟（分钟）</label>
          <input type="number" value={s.pomodoroMin} min={10} max={90}
            onChange={(e) => setS({ ...s, pomodoroMin: Number(e.target.value) })} />
          <div style={{ marginTop: 20 }} className="row">
            <button onClick={save}><IconCheck /> 保存设置</button>
            {saved && <span className="tag ok">已保存</span>}
          </div>
        </div>

        <div className="card">
          <h3><IconPulse /> 后端信息</h3>
          <div className="kv"><span className="k">API 基址</span><span className="v mono">{api.base}</span></div>
          <div className="kv"><span className="k">版本</span><span className="v">{backend?.version || '不可达'}</span></div>
          <h3 style={{ marginTop: 20 }}><IconDatabase /> 子系统</h3>
          <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
            {backend?.subsystems
              ? Object.entries(backend.subsystems).map(([k, v]) => (
                <span key={k} className={`tag ${v ? 'ok' : 'bad'}`}>{k}</span>
              ))
              : <span className="muted">后端未启动，无法获取子系统状态</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
