import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import {
  IconGraduation, IconBook, IconPulse, IconReview, IconGraph,
  IconPlus, IconSpark, IconBolt, IconCheck, IconSettings, IconClock
} from '../components/Icons.jsx';

export default function HeroHome({ events, connected }) {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [subjects, setSubjects] = useState([]);
  const [llmCfg, setLlmCfg] = useState(null);
  const [importOpen, setImportOpen] = useState(false);
  const [imp, setImp] = useState({ name: '', md: '', status: null });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const userId = localStorage.getItem('aitutor.user') || 'demo-user';

  useEffect(() => {
    api.listSubjects(userId).then(setSubjects).catch(() => setSubjects([]));
    api.getLlmSettings().then(setLlmCfg).catch(() => setLlmCfg(null));
  }, [userId]);

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    const text = prompt.trim();
    if (!text) {
      if (subjects.length > 0) {
        navigate('/learn');
      } else {
        setImportOpen(true);
      }
      return;
    }

    // 检查是否与已有科目名匹配
    const match = subjects.find(
      (s) => s.display_name?.toLowerCase() === text.toLowerCase() || s.subject_id === text
    );

    if (match) {
      navigate('/learn');
    } else {
      // 弹出导入并自动填入科目名称
      setImp({ name: text, md: `# ${text}\n\n## 核心概念\n\n- 定义与基本原理...\n`, status: null });
      setImportOpen(true);
    }
  };

  const handleImportSubmit = async () => {
    if (!imp.name.trim() || !imp.md.trim()) return;
    setErr(null);
    setImp((s) => ({ ...s, status: '提交中…' }));
    setBusy(true);
    try {
      const { task_id } = await api.importSubject(userId, imp.name.trim(), imp.md);
      for (;;) {
        await new Promise((r) => setTimeout(r, 800));
        const t = await api.getTask(task_id);
        if (t.state === 'succeeded') {
          setImp({ name: '', md: '', status: null });
          setImportOpen(false);
          navigate('/learn');
          break;
        }
        if (t.state === 'failed') {
          setImp((s) => ({ ...s, status: null }));
          setErr(`建科目失败：${t.error || '未知错误'}`);
          break;
        }
        setImp((s) => ({ ...s, status: `${t.message || '处理中'} ${Math.round((t.progress || 0) * 100)}%` }));
      }
    } catch (e) {
      setImp((s) => ({ ...s, status: null }));
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const modelName = llmCfg?.model || 'DeepSeek-V3';

  return (
    <div className="hero-page">
      <main className="hero">
        <div className="hero-badge">
          <span className="hero-badge-dot"></span>
          <span>v3.0 七层认知架构 · 48 小时极速掌握</span>
        </div>

        <h1 className="h1">
          48 小时学完一科 · 私人 AI 辅导
        </h1>

        <p className="hero-subtext">
          抽章节骨架 ➔ 建知识图谱 ➔ BKT 自适应摸底教学 ➔ FSRS-5 遗忘曲线复习
        </p>

        <form className="composer-card" onSubmit={handleSend}>
          <input
            className="composer-input"
            type="text"
            placeholder="输入想学的学科名称、知识点，或按 Enter 开学..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />

          <div className="tools">
            <div className="chips">
              <button
                className="chip"
                type="button"
                onClick={() => setImportOpen(true)}
                title="导入 Markdown / PDF 资料"
              >
                <IconPlus />
                <span>导入资料</span>
              </button>

              <button
                className="chip"
                type="button"
                onClick={() => navigate('/diagnose')}
                title="查看薄弱概念诊断"
              >
                <IconPulse />
                <span>薄弱突破</span>
              </button>

              <button
                className="chip"
                type="button"
                onClick={() => navigate('/review')}
                title="FSRS 遗忘曲线复习队列"
              >
                <IconReview />
                <span>今日复习</span>
              </button>

              <button
                className="chip"
                type="button"
                onClick={() => navigate('/graph')}
                title="查看 D3 知识图谱"
              >
                <IconGraph />
                <span>知识图谱</span>
              </button>
            </div>

            <div className="right">
              <button
                className="model"
                type="button"
                onClick={() => navigate('/settings')}
                title="切换模型或配置 API Key"
              >
                <IconSpark style={{ width: 14, height: 14 }} />
                <span>{modelName}</span>
              </button>

              <button
                className="send"
                type="submit"
                aria-label="开始学习"
                title="开启学习"
              >
                <IconBolt style={{ width: 16, height: 16 }} />
              </button>
            </div>
          </div>
        </form>

        {subjects.length > 0 && (
          <div className="hero-quick-subjects">
            <span className="hqs-label">快速继续：</span>
            {subjects.slice(0, 5).map((s) => (
              <button
                key={s.subject_id}
                className="hqs-btn"
                onClick={() => navigate('/learn')}
              >
                <IconBook style={{ width: 12, height: 12 }} />
                <span>{s.display_name}</span>
              </button>
            ))}
          </div>
        )}
      </main>

      <footer className="proof">
        <p className="proof-caption">Powered by v3.0 7-Layer Cognitive Architecture</p>
        <div className="proof-pills">
          <div className="proof-pill">
            <span className="pp-dot ok"></span>
            <span>BKT 掌握度引擎</span>
          </div>
          <div className="proof-pill">
            <span className="pp-dot info"></span>
            <span>FSRS-5 遗忘拟合</span>
          </div>
          <div className="proof-pill">
            <span className="pp-dot warn"></span>
            <span>PGFGA 心流回路</span>
          </div>
          <div className="proof-pill">
            <span className="pp-dot ok"></span>
            <span>939 项真测全绿</span>
          </div>
        </div>
      </footer>

      {importOpen && (
        <div className="overlay" onClick={() => !busy && setImportOpen(false)}>
          <div className="modal import-modal" onClick={(e) => e.stopPropagation()}>
            <h2><IconPlus /> 导入资料新建科目</h2>
            <p className="muted">粘贴带 <code>#</code> 一级标题、<code>##</code> 二级标题的 Markdown 格式讲义或笔记。</p>
            {err && <div className="banner error">{err}</div>}
            <label>科目名称</label>
            <input
              type="text"
              placeholder="例如：微积分下 / 数据结构 / 操作系统"
              value={imp.name}
              onChange={(e) => setImp({ ...imp, name: e.target.value })}
            />
            <label>Markdown 资料内容</label>
            <textarea
              rows={8}
              placeholder="# 第一章 导数与微分&#10;## 导数的定义&#10;导数描述了函数在某一点处的变化率..."
              value={imp.md}
              onChange={(e) => setImp({ ...imp, md: e.target.value })}
            />
            <div className="row" style={{ marginTop: 14, justifyContent: 'flex-end', gap: 10 }}>
              <button className="ghost" disabled={busy} onClick={() => setImportOpen(false)}>取消</button>
              <button className="primary" disabled={busy || !imp.name || !imp.md} onClick={handleImportSubmit}>
                {imp.status || '开始构建知识图谱'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
