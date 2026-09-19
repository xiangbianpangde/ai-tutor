# 前端任务包：Web 会话流与 MCP 动作卡片

> **面向成员**：前端研发（新手友好型）
> **前置技能要求**：了解基本的 HTML/CSS 与 JavaScript 语法；无需深奥的 React 高级原理，照猫画虎复用现有组件即可。
> **目标**：在现有 Web 客户端中，实现类似 Claude/ChatGPT 的自然会话流，并将底层强大的 4 个 MCP 核心能力（知识抽取、测验出题、导图生成、心流状态）包装成直观震撼的“交互式智能卡片”，用于比赛现场演示。

---

## 一、 任务目标与交付物

### 1. 核心职责
当前系统的 [LearnCenter.jsx](file:///Users/xbpd/Projects/ai-tutor/frontend/renderer/src/pages/LearnCenter.jsx) 是固定式“出题-作答-下一题”题目列表。你的核心任务是**将其升级为现代化的会话式智能辅导界面**：
1. **流畅的消息气泡流**：支持学生自由提问、导师启发式讲解、自动滚屏、加载动效。
2. **MCP 工具动作卡片（Tool Cards）**：当系统触发 MCP 动作时，在聊天流中不仅展示纯文本，更展示可交互的卡片：
   * **知识点名片（Knowledge Card）**：展示概念定义、核心要点、以及“在图谱中定位”按钮。
   * **动态测验卡片（Quiz Card）**：支持单选/输入作答、即时判分变色、展示正确解析。
   * **复习产物卡片（Digest Card）**：展示生成的思维导图缩略图、HTML 闪卡预览或“一键导出”按钮。
   * **心流状态微徽章（Flow Badge）**：显示“当前心流：专注”、“学习精力：充沛”，让评委一眼看到我们的心理学算法在运作！
3. **快捷指令栏（Action Chips / Shortcuts）**：在输入框上方提供快捷按钮（如：“🧩 生成测验”、“🗺️ 查看思维导图”、“💡 费曼挑战”），方便比赛答辩时一键点击演示。

### 2. 交付成果物
* **核心组件代码**：`frontend/renderer/src/pages/ChatTutor.jsx`（或直接增强 `LearnCenter.jsx`）。
* **卡片组件目录**：`frontend/renderer/src/components/cards/`
  * `KnowledgeCard.jsx`
  * `QuizCard.jsx`
  * `DigestCard.jsx`
  * `FlowBadge.jsx`
* **交互体验视频/截图**：提供 2-3 张高清聊天与卡片交互截图供写手放入 PPT。

### 3. 明确非目标（新手千万别做）
* ❌ **不要改写全局构建配置**：不要改动 `vite.config.js`、`package.json` 中的依赖版本。
* ❌ **不要碰复杂底层协议**：不要自己手写底层 WebSocket 或长连接重连机制，复用 `useWebSocket.js` 或现有的 `api.js` 请求封装。
* ❌ **不要重写现有侧边栏**：保持原有的侧边栏路由体系，只需增加或替换页面即可。

---

## 二、 现有资产与脚手架（直接拿来用）

项目中已经有非常棒的基础设施，你不需要从零造轮子：

1. **API 客户端**：[`frontend/renderer/src/api.js`](file:///Users/xbpd/Projects/ai-tutor/frontend/renderer/src/api.js)
   * 已经封装好 `api.startSession`, `api.respond`, `api.nextAction`, `api.listSubjects` 等，你只需直接 `import { api } from '../api.js'` 并调用即可。
2. **精美矢量图标库**：[`frontend/renderer/src/components/Icons.jsx`](file:///Users/xbpd/Projects/ai-tutor/frontend/renderer/src/components/Icons.jsx)
   * 内置了十几种手绘风格的 SVG 图标：`IconLearn`, `IconSend`, `IconGraduation`, `IconAlert`, `IconCheck` 等。
3. **暖纸风设计样式**：[`frontend/renderer/src/styles.css`](file:///Users/xbpd/Projects/ai-tutor/frontend/renderer/src/styles.css)
   * 现成的 CSS 类名已调好字体、圆角、柔和阴影与按钮悬浮效果。

---

## 三、 新手极速上手学习计划（2 周分解）

### 阶段 1：破冰与环境就绪（Day 1 ~ Day 3）
* **第一天：启动前端**
  1. 终端进入目录：`cd frontend/renderer`
  2. 安装依赖并启动：
     ```bash
     npm install
     npm run dev
     ```
  3. 浏览器打开 `http://localhost:5173`，体验现有的页面：首页、学习中心、知识图谱等。
* **第二天：读懂核心代码**
  * 仔细阅读 [LearnCenter.jsx](file:///Users/xbpd/Projects/ai-tutor/frontend/renderer/src/pages/LearnCenter.jsx) 的第 30~130 行：
    * 重点理解 React 的两个最常用 Hook：`useState`（存聊天记录和输入框文本）与 `useEffect`（刚进页面拉取数据）。
* **第三天：完成第一个微改动（Hello World）**
  * 在 `LearnCenter.jsx` 里为每条消息加上一个小时间戳或者在输入框旁边加一个清空按钮，在浏览器看到变化并提一次 Git commit。

### 阶段 2：开发 MCP 工具卡片组件（Day 4 ~ Day 7）
* **目标**：不碰复杂后端，先用静态假数据把 3 种漂亮卡片做出来。
* **做法**：
  * 新建 `frontend/renderer/src/components/cards/QuizCard.jsx`：
    ```jsx
    import { useState } from 'react';

    export default function QuizCard({ question, options, onAnswer }) {
      const [selected, setSelected] = useState(null);
      const [submitted, setSubmitted] = useState(false);

      const handleSelect = (idx) => {
        if (submitted) return;
        setSelected(idx);
      };

      const handleSubmit = () => {
        if (selected === null) return;
        setSubmitted(true);
        if (onAnswer) onAnswer(options[selected]);
      };

      return (
        <div style={{
          background: '#fff',
          border: '1px solid #e2e8f0',
          borderRadius: '12px',
          padding: '16px',
          margin: '12px 0',
          boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
        }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', color: '#1e293b' }}>
            📝 互动测验：{question}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {options.map((opt, i) => (
              <button
                key={i}
                onClick={() => handleSelect(i)}
                style={{
                  textAlign: 'left',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  border: selected === i ? '2px solid #3b82f6' : '1px solid #cbd5e1',
                  background: selected === i ? '#eff6ff' : '#f8fafc',
                  cursor: submitted ? 'default' : 'pointer'
                }}
              >
                {String.fromCharCode(65 + i)}. {opt}
              </button>
            ))}
          </div>
          {!submitted && (
            <button
              onClick={handleSubmit}
              disabled={selected === null}
              style={{
                marginTop: '12px',
                padding: '6px 16px',
                background: selected === null ? '#94a3b8' : '#3b82f6',
                color: '#fff',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer'
              }}
            >
              提交答案
            </button>
          )}
        </div>
      );
    }
    ```
  * 同理做出 `KnowledgeCard.jsx`（展示概念名、定义、核心关键词标签）。

### 阶段 3：装配进会话流（Day 8 ~ Day 12）
* 将这些卡片挂载进消息流数组中：
  ```javascript
  // 消息对象结构示例
  const msg = {
    who: 'tutor', // 'user' 或 'tutor'
    text: '这个知识点是计算机操作系统的核心，请尝试完成这道测验：',
    card: {
      type: 'quiz', // 'quiz' | 'knowledge' | 'digest'
      data: {
        question: '什么是进程的并发执行？',
        options: ['同一时刻绝对并行', '宏观同时但微观交替', '两个进程共享同一程序计数器']
      }
    }
  };
  ```
* 渲染时根据 `msg.card.type` 条件渲染对应的卡片组件！

### 阶段 4：联调与 UI 细节打磨（Day 13 ~ Day 14）
* 和后端同学对齐接口，点击快捷指令（如“一键出题”）真实调用后端并展示返回的测验卡片。
* 加入自动滚动到聊天底部的效果（`scrollIntoView({ behavior: 'smooth' })`）。

---

## 四、 队长验收标准（Checklist）

完成以下几项即可找队长验收合入：
- [ ] 聊天流能够正常输入并发送消息，能够显示导师的回复气泡。
- [ ] 至少支持两类卡片（测验卡片 `QuizCard` 和知识卡片 `KnowledgeCard`）在聊天流中正确呈现。
- [ ] 点击测验卡片选项能够交互（选中、变色、提交）。
- [ ] 界面在 1366x768 常见笔记本分辨率下无横向滚动条或布局错乱。
- [ ] 运行 `npm run build` 打包无任何错误。
