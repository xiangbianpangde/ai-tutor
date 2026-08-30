import { useState } from 'react';
import { IconGraduation, IconSettings, IconTarget, IconSpark } from './Icons.jsx';

// 首次使用向导（#8 / spec 04 功能3）：3 步，可跳过 LLM 配置。
// 第 1 步与设置页同构：provider 预设 base_url/model，均可自定义；
// 完成时若 key 齐全则直接热应用到后端（失败不阻断，可在设置页重试）。
const STEPS = 3;

const PRESETS = {
  deepseek: { base_url: 'https://api.deepseek.com', model: 'deepseek-chat' },
  openai: { base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  ollama: { base_url: 'http://localhost:11434/v1', model: 'qwen2.5:7b' },
  custom: { base_url: '', model: '' },
};

export default function Wizard({ onClose }) {
  const [step, setStep] = useState(0);
  const [cfg, setCfg] = useState({ provider: 'deepseek', apiKey: '', base_url: '', model: '', dailyGoalMin: 45 });
  const [applyNote, setApplyNote] = useState(null);

  const setProvider = (provider) => {
    const preset = PRESETS[provider] || {};
    setCfg({ ...cfg, provider, base_url: preset.base_url ?? '', model: preset.model ?? '' });
  };

  const llmReady = () => Boolean(cfg.apiKey && cfg.base_url && cfg.model);

  const finish = async () => {
    localStorage.setItem('aitutor.settings', JSON.stringify(cfg));
    if (llmReady()) {
      try {
        const { api } = await import('../api.js');
        await api.applyLlmSettings({
          base_url: cfg.base_url, api_key: cfg.apiKey, model: cfg.model,
        });
        setApplyNote({ ok: true, text: 'LLM 配置已应用到后端' });
      } catch (e) {
        setApplyNote({ ok: false, text: `应用失败（可在设置页重试）：${e.message || e}` });
        return; // 留在向导让用户看到失败原因
      }
    }
    onClose();
  };

  return (
    <div className="overlay">
      <div className="modal">
        <h2><IconGraduation /> 欢迎使用 AI-Tutor</h2>
        <p className="muted">48 小时学完一科的私人 AI 辅导系统</p>
        <div className="steps">
          {Array.from({ length: STEPS }).map((_, i) => (
            <div key={i} className={`step-dot${i <= step ? ' active' : ''}`} />
          ))}
        </div>

        {step === 0 && (
          <div>
            <h3 className="card-title-serif" style={{ marginBottom: 4 }}>
              <IconSettings style={{ verticalAlign: '-3px' }} /> 1 · 配置 LLM API
            </h3>
            <label>Provider</label>
            <select value={cfg.provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="deepseek">DeepSeek</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama（本地）</option>
              <option value="custom">自定义（任意 OpenAI 兼容端点）</option>
            </select>
            <label>Base URL（可自定义）</label>
            <input type="text" value={cfg.base_url} placeholder="https://api.deepseek.com"
              onChange={(e) => setCfg({ ...cfg, base_url: e.target.value })} />
            <label>API Key</label>
            <input type="password" value={cfg.apiKey} placeholder="sk-…（没有？可跳过）"
              onChange={(e) => setCfg({ ...cfg, apiKey: e.target.value })} />
            <label>Model</label>
            <input type="text" value={cfg.model} placeholder="deepseek-chat"
              onChange={(e) => setCfg({ ...cfg, model: e.target.value })} />
            <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>
              没有 Key 也能用基础功能（拓扑排序 / 遗忘曲线 / 知识图谱），只是不能 LLM 判分。
              端点需 OpenAI 兼容；本地 Ollama 填 http://localhost:11434/v1。
            </p>
          </div>
        )}
        {step === 1 && (
          <div>
            <h3 className="card-title-serif" style={{ marginBottom: 4 }}>
              <IconTarget style={{ verticalAlign: '-3px' }} /> 2 · 学习偏好（可选）
            </h3>
            <label>每日学习目标（分钟）</label>
            <input type="number" value={cfg.dailyGoalMin} min={5} max={480}
              onChange={(e) => setCfg({ ...cfg, dailyGoalMin: Number(e.target.value) })} />
          </div>
        )}
        {step === 2 && (
          <div>
            <h3 className="card-title-serif" style={{ marginBottom: 6 }}>
              <IconSpark style={{ verticalAlign: '-3px' }} /> 3 · 开始使用
            </h3>
            <p className="muted">在「学习中心」导入一份带 # 标题的资料或选择已有科目开启会话；「知识图谱」可以直观查看概念网络与认知负荷。</p>
            {applyNote && (
              <p className={applyNote.ok ? 'tag ok' : 'tag bad'} style={{ marginTop: 8 }}>{applyNote.text}</p>
            )}
          </div>
        )}

        <div className="row" style={{ justifyContent: 'space-between', marginTop: 24 }}>
          <button className="ghost" onClick={onClose}>跳过</button>
          <div className="row">
            {step > 0 && <button className="ghost" onClick={() => setStep(step - 1)}>上一步</button>}
            {step < STEPS - 1
              ? <button onClick={() => setStep(step + 1)} disabled={step === 2 && Boolean(applyNote && !applyNote.ok)}>下一步</button>
              : <button onClick={finish} disabled={Boolean(applyNote && !applyNote.ok)}>
                  {llmReady() ? '完成并应用' : '完成'}
                </button>}
          </div>
        </div>
      </div>
    </div>
  );
}
