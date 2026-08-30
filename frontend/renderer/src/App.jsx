import { useState, useEffect } from 'react';
import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { useWebSocket } from './useWebSocket.js';
import { api } from './api.js';
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
  IconDashboard, IconLearn, IconGraph, IconReview, IconSettings, IconGraduation, IconPulse, IconTasks, IconBook, IconHistory,
} from './components/Icons.jsx';

const NAV = [
  { to: '/dashboard', label: '仪表盘', icon: IconDashboard },
  { to: '/diagnose', label: '薄弱诊断', icon: IconPulse },
  { to: '/learn', label: '学习中心', icon: IconLearn },
  { to: '/graph', label: '知识图谱', icon: IconGraph },
  { to: '/review', label: '复习', icon: IconReview },
  { to: '/tasks', label: '任务中心', icon: IconTasks },
  { to: '/plan', label: '学习计划', icon: IconBook },
  { to: '/history', label: '会话历史', icon: IconHistory },
  { to: '/settings', label: '设置', icon: IconSettings },
];

export default function App() {
  const { connected, events } = useWebSocket();
  const [showWizard, setShowWizard] = useState(false);

  useEffect(() => {
    // 首次启动（无 settings）→ 显示向导（#8）
    const done = localStorage.getItem('aitutor.onboarded');
    if (!done) setShowWizard(true);
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><IconGraduation size={20} /></span>
          <span>
            <div className="brand-name">AI-Tutor</div>
            <div className="brand-ver">48h · 私人辅导</div>
          </span>
        </div>
        <div className="nav-section">导航</div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <n.icon />
              <span className="nav-label">{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="conn">
          <span className={`dot ${connected ? 'on' : 'off'}`} />
          <span className="conn-label">{connected ? '实时连接正常' : '正在连接后端…'}</span>
        </div>
      </aside>

      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
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
