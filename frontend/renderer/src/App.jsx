import { useState, useEffect } from 'react';
import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { useWebSocket } from './useWebSocket.js';
import { api } from './api.js';
import Dashboard from './pages/Dashboard.jsx';
import LearnCenter from './pages/LearnCenter.jsx';
import KnowledgeGraph from './pages/KnowledgeGraph.jsx';
import ReviewPage from './pages/ReviewPage.jsx';
import Settings from './pages/Settings.jsx';
import Wizard from './components/Wizard.jsx';

const NAV = [
  { to: '/dashboard', label: '仪表盘', icon: '◧' },
  { to: '/learn', label: '学习中心', icon: '✎' },
  { to: '/graph', label: '知识图谱', icon: '⬡' },
  { to: '/review', label: '复习', icon: '↻' },
  { to: '/settings', label: '设置', icon: '⚙' },
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
          <span className="brand-mark">🎓</span>
          <span className="brand-name">AI-Tutor</span>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <span className="nav-icon">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="conn">
          <span className={`dot ${connected ? 'on' : 'off'}`} />
          {connected ? '实时已连接' : '连接中…'}
        </div>
      </aside>

      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard events={events} connected={connected} />} />
          <Route path="/learn" element={<LearnCenter events={events} />} />
          <Route path="/graph" element={<KnowledgeGraph />} />
          <Route path="/review" element={<ReviewPage />} />
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
