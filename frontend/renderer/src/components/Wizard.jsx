import { useState } from 'react';
import { api } from '../api.js';
import { IconGraduation, IconSettings, IconTarget, IconSpark } from './Icons.jsx';

// 首次使用向导（#8 / spec 04 功能3）：3 步，可跳过 LLM 配置。
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
        await api.applyLlmSettings({
          base_url: cfg.base_url, api_key: cfg.apiKey, model: cfg.model,
        });
        setApplyNote({ ok: true, text: 'LLM 配置已应用到后端' });
      } catch (e) {
        setApplyNote({ ok: false, text: `应用失败（可在设置页重试）：${e.message || e}` });
        return;
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
            <h3 style={{ marginBottom: 8, fontSize: 16 }}>
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
            <input
              type="text"
              value={cfg.base_url}
              placeholder="https://api.deepseek.com"
              onChange={(e) => setCfg({ ...cfg, base_url: e.target.value })}
            />
            <label>API Key</label>
            <input
              type="password"
              value={cfg.apiKey}
              placeholder="sk-…（没有？可跳过）"
              onChange={(e) => setCfg({ ...cfg, apiKey: e.target.value })}
            />
            <label>Model</label>
            <input
              type="text"
              value={cfg.model}
              placeholder="deepseek-chat"
              onChange={(e) => setCfg({ ...cfg, model: e.target.value })}
            />
            <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
              没有 Key 也能使用基础功能（拓扑排序 / 遗忘曲线 / 知识图谱），配备 Key 则支持智能教学与判分。
            </p>
          </div>
        )}
        {step === 1 && (
          <div>
            <h3 style={{ marginBottom: 8, fontSize: 16 }}>
              <IconTarget style={{ verticalAlign: '-3px' }} /> 2 · 学习偏好（可选）
            </h3>
            <label>每日学习目标（分钟）</label>
            <input
              type="number"
              value={cfg.dailyGoalMin}
              min={5}
              max={480}
              onChange={(e) => setCfg({ ...cfg, dailyGoalMin: Number(e.target.value) })}
            />
          </div>
        )}
        {step === 2 && (
          <div>
            <h3 style={{ marginBottom: 8, fontSize: 16 }}>
              <IconSpark style={{ verticalAlign: '-3px' }} /> 3 · 开始使用
            </h3>
            <p className="muted">在「极速启动」输入学科或导入 Markdown 资料；在「知识图谱」直观查看概念依赖与认知负荷。</p>
            {applyNote && (
              <p className={applyNote.ok ? 'tag ok' : 'tag bad'} style={{ marginTop: 8 }}>{applyNote.text}</p>
            )}
          </div>
        )}

        <div className="row" style={{ justifyContent: 'space-between', marginTop: 22 }}>
          {step > 0 ? (
            <button className="ghost" onClick={() => setStep((s) => s - 1)}>上一步</button>
          ) : <span />}
          {step < STEPS - 1 ? (
            <button className="primary" onClick={() => setStep((s) => s + 1)}>下一步</button>
          ) : (
            <button className="primary" onClick={finish}>进入系统</button>
          )}
        </div>
      </div>
    </div>
  );
}
