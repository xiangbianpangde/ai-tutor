import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { IconSettings, IconCheck, IconPulse, IconDatabase } from '../components/Icons.jsx';

// 设置：LLM provider/base_url/model/key（存 localStorage 并热应用到后端）
// + 学习偏好 + 后端信息。key 只存本机 localStorage 与后端进程内存，
// 不落盘、不入日志；请求只发往用户显式配置的 base_url。
const KEY = 'aitutor.settings';

// 各 provider 的默认端点/模型（用户可在 UI 覆盖 base_url 与 model）。
const PROVIDER_PRESETS = {
  deepseek: { base_url: 'https://api.deepseek.com', model: 'deepseek-chat' },
  openai: { base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  ollama: { base_url: 'http://localhost:11434/v1', model: 'qwen2.5:7b' },
  custom: { base_url: '', model: '' },
};

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || 'null') || {};
  } catch {
    return {};
  }
}

export default function Settings() {
  const saved = loadSaved();
  const preset = PROVIDER_PRESETS[saved.provider] || PROVIDER_PRESETS.deepseek;
  const [s, setS] = useState({
    provider: 'deepseek',
    apiKey: '',
    baseUrl: '',
    model: '',
    dailyGoalMin: 45,
    pomodoroMin: 25,
    ...saved,
    // 旧版本存储缺 baseUrl/model：补 provider 预设，避免空端点
    baseUrl: saved.baseUrl || preset.base_url || '',
    model: saved.model || preset.model || '',
  });
  const [savedFlag, setSaved] = useState(false);
  const [backend, setBackend] = useState(null);
  const [effective, setEffective] = useState(null);
  const [testState, setTestState] = useState(null); // {ok, text}

  useEffect(() => {
    api.systemHealth().then(setBackend).catch(() => setBackend(null));
    api.getLlmSettings().then(setEffective).catch(() => setEffective(null));
  }, []);

  const setProvider = (provider) => {
    const preset = PROVIDER_PRESETS[provider] || {};
    setS({ ...s, provider, baseUrl: preset.base_url ?? '', model: preset.model ?? '' });
    setTestState(null);
  };

  const buildCfg = () => ({
    base_url: (s.baseUrl || '').trim(),
    api_key: s.apiKey || '',
    model: (s.model || '').trim(),
  });

  const validate = () => {
    const cfg = buildCfg();
    if (!/^https?:\/\//.test(cfg.base_url)) return 'Base URL 必须以 http:// 或 https:// 开头';
    if (!cfg.api_key) return 'API Key 不能为空';
    if (!cfg.model) return 'Model 不能为空';
    return null;
  };

  const persist = () => localStorage.setItem(KEY, JSON.stringify(s));

  const save = async () => {
    const problem = validate();
    if (problem) { setTestState({ ok: false, text: problem }); return; }
    try {
      // 保存并热应用到后端（生效无需重启）
      setEffective(await api.applyLlmSettings(buildCfg()));
      persist();
      setSaved(true);
      setTestState({ ok: true, text: '已保存并应用到后端' });
      setTimeout(() => setSaved(false), 1800);
    } catch (e) {
      setTestState({ ok: false, text: String(e.message || e) });
    }
  };

  const testConnection = async () => {
    const problem = validate();
    if (problem) { setTestState({ ok: false, text: problem }); return; }
    setTestState({ ok: null, text: '探测中…' });
    try {
      const r = await api.testLlmSettings(buildCfg());
      if (r.ok) setTestState({ ok: true, text: `连通（${r.model}，${r.latency_ms}ms）` });
      else setTestState({ ok: false, text: r.error || '探测失败' });
    } catch (e) {
      setTestState({ ok: false, text: String(e.message || e) });
    }
  };

  const needsKey = s.provider !== 'none';

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">设置</h1>
          <p className="page-sub">LLM 配置与学习偏好（key 只存本机，热应用无需重启）</p>
        </div>
      </div>

      <div className="grid cols-2" style={{ alignItems: 'start' }}>
        <div className="card">
          <h3><IconSettings /> LLM 配置</h3>
          <label>Provider</label>
          <select value={s.provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama（本地）</option>
            <option value="custom">自定义（任意 OpenAI 兼容端点）</option>
            <option value="none">暂不配置（仅基础功能）</option>
          </select>
          {needsKey && (
            <>
              <label>Base URL（OpenAI 兼容，可自定义）</label>
              <input type="text" value={s.baseUrl}
                placeholder="https://api.deepseek.com"
                onChange={(e) => setS({ ...s, baseUrl: e.target.value })} />
              <label>API Key</label>
              <input type="password" value={s.apiKey} placeholder="sk-…"
                onChange={(e) => setS({ ...s, apiKey: e.target.value })} />
              <label>Model</label>
              <input type="text" value={s.model} placeholder="deepseek-chat"
                onChange={(e) => setS({ ...s, model: e.target.value })} />
            </>
          )}
          <label>每日目标（分钟）</label>
          <input type="number" value={s.dailyGoalMin} min={5} max={480}
            onChange={(e) => setS({ ...s, dailyGoalMin: Number(e.target.value) })} />
          <label>番茄钟（分钟）</label>
          <input type="number" value={s.pomodoroMin} min={10} max={90}
            onChange={(e) => setS({ ...s, pomodoroMin: Number(e.target.value) })} />
          <div style={{ marginTop: 20 }} className="row">
            <button onClick={save}><IconCheck /> 保存并应用</button>
            {needsKey && (
              <button className="btn-ghost" onClick={testConnection} disabled={testState && testState.ok === null}>
                测试连接
              </button>
            )}
            {saved && <span className="tag ok">已保存</span>}
          </div>
          {testState && (
            <div className="kv" style={{ marginTop: 10 }}>
              <span className={testState.ok === true ? 'tag ok' : testState.ok === false ? 'tag bad' : 'muted'}>
                {testState.text}
              </span>
            </div>
          )}
          {effective && (
            <div className="kv" style={{ marginTop: 12 }}>
              <span className="k">当前生效</span>
              <span className="v mono">
                {effective.provider === 'local_judge'
                  ? '本地判分器（未配置真 LLM）'
                  : `${effective.provider} · ${effective.model || ''} · ${effective.base_url || ''} · key ${effective.api_key_masked || '***'}`}
              </span>
            </div>
          )}
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
