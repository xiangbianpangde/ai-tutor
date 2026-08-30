import { useState, useEffect } from 'react';
import { api } from '../api.js';
import {
  IconSettings, IconCheck, IconPulse, IconDatabase, IconReset, IconEye, IconEyeOff,
} from '../components/Icons.jsx';

// 设置：LLM provider/base_url/model/key（存 localStorage 并热应用到后端）
// + 学习偏好（每日目标/番茄钟，由复习页消费）+ 后端信息。
// key 只存本机 localStorage 与后端进程内存；不落盘、不入日志；
// 请求只发往用户显式配置的 base_url。
const KEY = 'aitutor.settings';

const PROVIDER_PRESETS = {
  deepseek: { base_url: 'https://api.deepseek.com', model: 'deepseek-chat' },
  openai: { base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  ollama: { base_url: 'http://localhost:11434/v1', model: 'qwen2.5:7b' },
  custom: { base_url: '', model: '' },
};

// source 说明（后端返回：runtime / injected / fallback）
const SOURCE_NOTE = {
  runtime: '本次进程内的热应用；重启后端后回到环境变量/本地判分器，重新保存即恢复。',
  injected: '由宿主注入（测试/嵌入场景）；生产不会出现。',
  fallback: '未配置真 LLM，当前为本地判分器（基础模式）。',
};

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || 'null') || {};
  } catch {
    return {};
  }
}

export function readPrefs() {
  const saved = loadSaved();
  return {
    dailyGoalMin: Number(saved.dailyGoalMin) || 45,
    pomodoroMin: Number(saved.pomodoroMin) || 25,
  };
}

export default function Settings() {
  const saved = loadSaved();
  const preset = PROVIDER_PRESETS[saved.provider] || PROVIDER_PRESETS.deepseek;
  const stored = {
    provider: 'deepseek',
    apiKey: '',
    baseUrl: '',
    model: '',
    dailyGoalMin: 45,
    pomodoroMin: 25,
    ...saved,
  };
  const [s, setS] = useState({
    provider: stored.provider,
    apiKey: stored.apiKey,
    baseUrl: stored.baseUrl || preset.base_url || '',
    model: stored.model || preset.model || '',
    dailyGoalMin: stored.dailyGoalMin,
    pomodoroMin: stored.pomodoroMin,
  });
  const [savedFlag, setSaved] = useState(false);
  const [backend, setBackend] = useState(null);
  const [effective, setEffective] = useState(null);
  const [testState, setTestState] = useState(null); // {ok, text}
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    api.systemHealth().then(setBackend).catch(() => setBackend(null));
    api.getLlmSettings().then(setEffective).catch(() => setEffective(null));
  }, []);

  const setProvider = (provider) => {
    const p = PROVIDER_PRESETS[provider] || {};
    setS({ ...s, provider, baseUrl: p.base_url ?? '', model: p.model ?? '' });
    setTestState(null);
  };

  const buildCfg = () => ({
    base_url: (s.baseUrl || '').trim(),
    api_key: s.apiKey || '',
    model: (s.model || '').trim(),
  });

  const validate = () => {
    if (!/^https?:\/\//.test(s.baseUrl.trim())) return 'Base URL 必须以 http:// 或 https:// 开头';
    if (!s.apiKey.trim()) return 'API Key 不能为空';
    if (!s.model.trim()) return 'Model 不能为空';
    return null;
  };

  const persist = () => localStorage.setItem(KEY, JSON.stringify(s));

  const save = async () => {
    // 单步：先探测（防止保存坏端点），成功才应用并落盘
    setTestState({ ok: null, text: '探测中…' });
    try {
      const probed = await api.testLlmSettings(buildCfg());
      if (!probed.ok) {
        setTestState({ ok: false, text: `连接失败：${probed.error || '未知原因'}，未保存` });
        return;
      }
      setEffective(await api.applyLlmSettings(buildCfg()));
      persist();
      setSaved(true);
      setTestState({ ok: true, text: `已应用（${probed.model}，${probed.latency_ms}ms）` });
      setTimeout(() => setSaved(false), 1800);
    } catch (e) {
      setTestState({ ok: false, text: `保存失败：${String(e.message || e)}，未保存` });
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
      setTestState({ ok: false, text: `探测失败：${String(e.message || e)}` });
    }
  };

  const resetLlm = async () => {
    try {
      const after = await api.resetLlmSettings();
      setEffective(after);
      setTestState({ ok: true, text: '已切回环境/本地判分器（配置保留，可随时重新应用）' });
    } catch (e) {
      setTestState({ ok: false, text: String(e.message || e) });
    }
  };

  const clearAll = async () => {
    localStorage.removeItem(KEY);
    setS({ provider: 'none', apiKey: '', baseUrl: '', model: '', dailyGoalMin: 45, pomodoroMin: 25 });
    try {
      setEffective(await api.resetLlmSettings());
      setTestState({ ok: true, text: '已清除本机配置并切回默认' });
    } catch (e) {
      setTestState({ ok: false, text: String(e.message || e) });
    }
  };

  const needsKey = s.provider !== 'none';
  const sourceText = effective ? (SOURCE_NOTE[effective.source] || '') : '';

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
              <div className="row" style={{ gap: 6 }}>
                <input type={showKey ? 'text' : 'password'} value={s.apiKey}
                  placeholder="sk-…" style={{ flex: 1 }}
                  onChange={(e) => setS({ ...s, apiKey: e.target.value })} />
                <button className="ghost sm" onClick={() => setShowKey(!showKey)}
                  title={showKey ? '隐藏 Key' : '显示 Key'}>
                  {showKey ? <IconEyeOff size={15} /> : <IconEye size={15} />}
                </button>
              </div>
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
          <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            每日目标已生效于「复习」页的建议复习量；番茄钟保留（将在专注计时接入后使用）。
          </div>
          <div style={{ marginTop: 20 }} className="row">
            <button onClick={save}><IconCheck /> 保存并应用</button>
            {needsKey && (
              <button className="btn-ghost" onClick={testConnection} disabled={testState && testState.ok === null}>
                测试连接
              </button>
            )}
            {saved && <span className="tag ok">已保存</span>}
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <button className="ghost sm" onClick={resetLlm}>重置 LLM</button>
            <button className="ghost sm" onClick={clearAll}>清除本机配置</button>
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
              {sourceText && <span className="muted" style={{ display: 'block', marginTop: 4, fontSize: 12 }}>{sourceText}</span>}
            </div>
          )}
        </div>

        <div className="card">
          <h3><IconPulse /> 后端信息</h3>
          <div className="kv"><span className="k">API 基址</span><span className="v mono">{api.base}</span></div>
          <div className="kv"><span className="k">版本</span><span className="v">{backend?.version || '不可达'}</span></div>
          <div className="kv"><span className="k">LLM 生效来源</span><span className="v mono">{effective?.source || '—'}</span></div>
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
