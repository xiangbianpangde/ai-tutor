import { useState } from 'react';

// 首次使用向导（#8 / spec 04 功能3）：3 步，可跳过 LLM 配置。
const STEPS = 3;

export default function Wizard({ onClose }) {
  const [step, setStep] = useState(0);
  const [cfg, setCfg] = useState({ provider: 'deepseek', apiKey: '', dailyGoalMin: 45 });

  const finish = () => {
    localStorage.setItem('aitutor.settings', JSON.stringify(cfg));
    onClose();
  };

  return (
    <div className="overlay">
      <div className="modal">
        <h2>欢迎使用 AI-Tutor 🎓</h2>
        <p className="muted">48 小时学完一科的私人 AI 辅导系统</p>
        <div className="steps">
          {Array.from({ length: STEPS }).map((_, i) => (
            <div key={i} className={`step-dot${i <= step ? ' active' : ''}`} />
          ))}
        </div>

        {step === 0 && (
          <div>
            <h3>1 · 配置 LLM API</h3>
            <label>Provider</label>
            <select value={cfg.provider} onChange={(e) => setCfg({ ...cfg, provider: e.target.value })}>
              <option value="deepseek">DeepSeek</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama（本地）</option>
            </select>
            <label>API Key</label>
            <input type="password" value={cfg.apiKey} placeholder="sk-…（没有？可跳过）"
              onChange={(e) => setCfg({ ...cfg, apiKey: e.target.value })} />
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              没有 Key 也能用基础功能（拓扑排序 / 遗忘曲线 / 知识图谱），只是不能 LLM 判分。
            </p>
          </div>
        )}
        {step === 1 && (
          <div>
            <h3>2 · 学习偏好（可选）</h3>
            <label>每日学习目标（分钟）</label>
            <input type="number" value={cfg.dailyGoalMin}
              onChange={(e) => setCfg({ ...cfg, dailyGoalMin: Number(e.target.value) })} />
          </div>
        )}
        {step === 2 && (
          <div>
            <h3>3 · 开始使用！</h3>
            <p className="muted">在「学习中心」开启会话，或先在「知识图谱」看看已有科目。</p>
          </div>
        )}

        <div className="row" style={{ justifyContent: 'space-between', marginTop: 22 }}>
          <button className="ghost" onClick={onClose}>跳过</button>
          <div className="row">
            {step > 0 && <button className="ghost" onClick={() => setStep(step - 1)}>上一步</button>}
            {step < STEPS - 1
              ? <button onClick={() => setStep(step + 1)}>下一步</button>
              : <button onClick={finish}>完成</button>}
          </div>
        </div>
      </div>
    </div>
  );
}
