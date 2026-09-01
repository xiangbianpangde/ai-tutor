import { useState, useEffect } from 'react';
import { Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useWebSocket } from './useWebSocket.js';
import { api } from './api.js';
import HeroHome from './pages/HeroHome.jsx';
import Dashboard from './pages/Dashboard.jsx';
import LearnCenter from './pages/LearnCenter.jsx';
import KnowledgeGraph from './pages/KnowledgeGraph.jsx';
import ReviewPage from './pages/ReviewPage.jsx';
import Settings from './pages/Settings.jsx';
import Diagnose from './pages/Diagnose.jsx';
import Tasks from './pages/Tasks.jsx';
import Plan from './pages/Plan.jsx';
import History from './pages/History.jsx';
import Wizard from './components/Wizard.jsx';
import {
  IconDashboard, IconLearn, IconGraph, IconReview, IconSettings, IconGraduation,
  IconPulse, IconTasks, IconBook, IconHistory, IconSpark
} from './components/Icons.jsx';

const NAV = [
  { to: '/', label: '极速启动', icon: IconSpark },
  { to: '/dashboard', label: '仪表盘', icon: IconDashboard },
  { to: '/learn', label: '学习中心', icon: IconLearn },
  { to: '/graph', label: '知识图谱', icon: IconGraph },
  { to: '/diagnose', label: '薄弱诊断', icon: IconPulse },
  { to: '/review', label: '复习', icon: IconReview },
  { to: '/plan', label: '学习计划', icon: IconBook },
  { to: '/history', label: '历史', icon: IconHistory },
];

export default function App() {
  const { connected, events } = useWebSocket();
  const [showWizard, setShowWizard] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    // 首次启动（无 settings）→ 显示向导
    const done = localStorage.getItem('aitutor.onboarded');
    if (!done) setShowWizard(true);
  }, []);

  const isHero = location.pathname === '/';

  return (
    <div className={`stage${isHero ? ' is-hero' : ''}`}>
      {/* Hero: 电影感日落循环视频(深色舞台);其余页面:暖纸世界地图底纹 */}
      {isHero ? (
        <video
          className="stage-video"
          autoPlay
          muted
          loop
          playsInline
          poster="./hero-bg.jpg"
          aria-hidden="true"
        >
          <source src="./hero-loop.mp4" type="video/mp4" />
        </video>
      ) : (
        <video
          className="stage-video"
          autoPlay
          muted
          loop
          playsInline
          poster="./bg-warm.jpg"
          aria-hidden="true"
        >
          <source src="./bg-loop.mp4" type="video/mp4" />
        </video>
      )}

      <div className={`stage-overlay${isHero ? ' hero-overlay' : ''}`} />

      {/* 主界面框架 */}
      <div className="frame">
        <header className={`nav-header${isHero ? ' nav-header--cinematic' : ''}`}>
          <NavLink to="/" className="brand">
            <span className="brand-mark">
              <IconGraduation size={20} />
            </span>
            <span>
              <div className="brand-name">AI-Tutor</div>
              <div className="brand-ver">48h · 私人辅导</div>
            </span>
          </NavLink>

          <nav className="nav-links">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                end={n.to === '/'}
              >
                <n.icon style={{ width: 14, height: 14 }} />
                <span>{n.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="nav-actions">
            <div className="conn-badge" title={connected ? 'WebSocket 实时连接正常' : '正在连接后端…'}>
              <span className={`conn-dot ${connected ? 'on' : 'off'}`} />
              <span>{connected ? '在线' : '离线'}</span>
            </div>

            <button
              className="nav-btn"
              onClick={() => navigate('/tasks')}
              title="后台任务中心"
            >
              <IconTasks style={{ width: 14, height: 14 }} />
              <span>任务</span>
            </button>

            <button
              className="nav-btn"
              onClick={() => navigate('/settings')}
              title="系统与模型设置"
            >
              <IconSettings style={{ width: 14, height: 14 }} />
            </button>
          </div>
        </header>

        <main className={`content-area${isHero ? ' hero-mode' : ''}`}>
          <Routes>
            <Route path="/" element={<HeroHome events={events} connected={connected} />} />
            <Route path="/dashboard" element={<Dashboard events={events} connected={connected} />} />
            <Route path="/diagnose" element={<Diagnose />} />
            <Route path="/learn" element={<LearnCenter events={events} />} />
            <Route path="/graph" element={<KnowledgeGraph />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/plan" element={<Plan />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>

      {showWizard && (
        <Wizard
          onClose={() => {
            localStorage.setItem('aitutor.onboarded', '1');
            setShowWizard(false);
          }}
        />
      )}
    </div>
  );
}

export { api };
