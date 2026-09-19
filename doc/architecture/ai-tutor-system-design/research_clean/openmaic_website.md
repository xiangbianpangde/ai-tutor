# openmaic_website

Source: https://openmaic.io/

Overview

## Reimagining Online Education with LLM-Driven Agents

OpenMAIC (Open Multi-Agent Interactive Classroom) is an open-source AI platform developed by the THU-MAIC team at **Tsinghua University**. It is designed to fundamentally transform online education — moving beyond passive video lectures toward active, personalized, and social AI-driven classrooms. By leveraging large language model (LLM) orchestration and multi-agent collaboration, OpenMAIC generates complete interactive lessons from any topic description or uploaded document. 

The platform simulates an authentic classroom environment populated by AI teachers with distinct teaching styles, AI teaching assistants who provide supplementary help, and AI classmates who participate in discussions and debates. This multi-agent approach recreates the social dynamics of a real classroom, fostering deeper engagement and more effective learning outcomes. OpenMAIC has been validated with over 700 students at Tsinghua University across more than two years of testing and iteration, proving its effectiveness in real-world educational settings. 

### Platform Highlights

  * One-click lesson generation from any topic or document
  * Multi-agent classroom with AI teachers and peers
  * Rich scene types: slides, quizzes, simulations, PBL
  * Whiteboard drawing and TTS voice narration
  * Export to editable PowerPoint (.pptx) or interactive HTML
  * OpenClaw integration for Feishu, Slack, Telegram, and more
  * Supports OpenAI, Anthropic, Google Gemini, DeepSeek
  * Docker, Vercel, and self-hosted deployment options

Features

## A Complete AI Classroom Experience

OpenMAIC delivers a rich, multi-modal learning experience through its two-stage generation pipeline and real-time multi-agent interaction system. 

### Intelligent Slide Lectures

AI teachers deliver lectures with natural voice narration, spotlight effects, and laser pointer animations — replicating the experience of a live classroom presentation with rich visual aids.

### Interactive Quizzes & AI Grading

Automatically generated quizzes — single choice, multiple choice, and short answer — aligned with learning objectives. The AI grading system provides instant, detailed feedback and identifies knowledge gaps to suggest personalized learning paths.

### Interactive HTML Simulations

Browser-based interactive experiments that bring abstract concepts to life through hands-on exploration — physics simulators, algorithm visualizations, flowcharts, and more, all generated automatically.

### Project-Based Learning (PBL)

Structured project activities where students choose roles and collaborate with AI agents on real-world projects with defined milestones and deliverables, encouraging applied problem-solving.

### Collaborative Whiteboard

AI agents draw on a shared whiteboard in real time — solving equations step by step, sketching flowcharts, illustrating diagrams, or writing formulas — making complex concepts visually intuitive.

### Voice Interaction & TTS

AI agents lecture using natural text-to-speech with multiple voice providers and customizable voices. Students can speak back via automatic speech recognition for hands-free participation in discussions and Q&A sessions.

Multi-Agent Interaction

## Dynamic Classroom Engagement Modes

OpenMAIC's multi-agent orchestration enables several interaction modes that mirror real classroom dynamics, each powered by LangGraph state machine management. 

### Classroom Discussion

AI agents proactively initiate topic-based discussions. Students can jump in at any time or be called on by the AI teacher, simulating natural classroom participation patterns.

### Roundtable Debate

Multiple AI agents with different personas and viewpoints debate a topic while using the whiteboard to illustrate their arguments, promoting critical thinking through exposure to diverse perspectives.

### Q&A Mode

Ask questions freely and receive comprehensive responses from the AI teacher, complete with supporting slides, diagrams, or real-time whiteboard drawings for visual explanation.

Architecture

## Technical Foundation

OpenMAIC is built on a modern web stack centered around **Next.js** , **React** , and **TypeScript** , with **Tailwind CSS** for the UI layer. The multi-agent orchestration layer is powered by **LangGraph** , which manages a state machine governing agent turns, discussions, and collaborative interactions. 

The lesson generation pipeline operates in two stages. The first stage analyzes user input — a topic description or uploaded document — and produces a structured lesson outline. The second stage transforms each outline item into rich multimedia scenes: slides with voice narration, quizzes with grading rubrics, interactive HTML simulations, or project-based learning activities. 

The platform supports multiple LLM providers including OpenAI, Anthropic, Google Gemini, DeepSeek, and any OpenAI-compatible API. The recommended default model is **Gemini 3 Flash** for the best balance of quality and speed, with Gemini 3.1 Pro available for highest quality output. An action execution engine handles 28+ action types — speech, whiteboard drawing, spotlight effects, laser pointer, and more. 

Frontend

Next.js + React + TypeScript + Tailwind CSS

Agent Orchestration

LangGraph multi-agent state machine

Generation Pipeline

Two-stage: Outline → Scene content

Action Engine

28+ action types (speech, whiteboard, effects)

LLM Providers

OpenAI, Anthropic, Gemini, DeepSeek, and more

Deployment

Docker, Vercel, or self-hosted

License

AGPL-3.0 (commercial licensing available)

Use Cases

## What You Can Build with OpenMAIC

From learning a new programming language to analyzing research papers, OpenMAIC adapts to a wide range of educational scenarios. 

Learn Programming from Scratch

Describe a topic like "Teach me Python from scratch in 30 minutes" and receive a complete lesson with slides, code examples, interactive exercises, and quizzes — all narrated by an AI instructor.

Analyze Research Papers

Upload a PDF of a research paper and OpenMAIC will break it down into digestible lessons, explaining key concepts with visual aids and interactive elements powered by the MinerU document parsing engine.

Explore Real-World Topics

Ask OpenMAIC to teach you how to play a board game, analyze stock market trends, or explain historical events — AI agents search the web for up-to-date information and present it in an engaging classroom format.

Generate from Chat Apps

With OpenClaw integration, generate classrooms directly from Feishu, Slack, Discord, Telegram, and 20+ messaging apps — no terminal required. Install with a single command: `clawhub install openmaic`.

Get OpenMAIC running locally in minutes. You will need Node.js 20 or later and pnpm 10 or later. 

1

### Clone & Install

Clone the repository and install dependencies using pnpm.

git clone https://github.com/THU-MAIC/OpenMAIC.git  
cd OpenMAIC  
pnpm install

2

### Configure

Copy the example environment file and add at least one LLM provider API key. Supported providers include OpenAI, Anthropic, Google Gemini, DeepSeek, and any OpenAI-compatible API.

# Add your API key(s):  
# OPENAI_API_KEY=sk-...  
# ANTHROPIC_API_KEY=sk-ant-...  
# GOOGLE_API_KEY=...

3

### Run

pnpm dev  
# Open http://localhost:3000

4

### Deploy (Optional)

Build for production and deploy to Vercel, Docker, or your own infrastructure.

pnpm build && pnpm start  
# Or with Docker:  
docker compose up --build

Research

## Academic Foundation & Validation

OpenMAIC is grounded in rigorous academic research conducted by the THU-MAIC team at Tsinghua University. The project introduces the MAIC (Multi-Agent Interactive Classroom) paradigm — a conceptual evolution from the MOOC (Massive Open Online Course) model — that leverages LLM-driven agents to create active, personalized, and socially rich learning environments. 

The platform has been validated through extensive real-world deployment with over 700 students at Tsinghua University across more than two years of testing, iteration, and refinement. This long-term validation demonstrates its effectiveness in genuine educational settings and provides a solid empirical foundation for its pedagogical approach. 

The underlying research has been published in the **Journal of Computer Science and Technology (JCST 2026)** under the title _"From MOOC to MAIC: Reimagine Online Teaching and Learning through LLM-driven Agents."_ The paper details the multi-agent architecture, generation pipeline, and educational outcomes observed during deployment. 

@Article{JCST-2509-16000, title = {From MOOC to MAIC: Reimagine Online Teaching and Learning through LLM-driven Agents}, journal = {Journal of Computer Science and Technology}, year = {2026}, doi = {10.1007/s11390-025-6000-0}, author = {Ji-Fan Yu and Daniel Zhang-Li and Zhe-Yuan Zhang and Yu-Cheng Wang and Hao-Xuan Li and Joy Jia Yin Lim and Zhan-Xin Hao and Shang-Qing Tu and Lu Zhang and Xu-Sheng Dai and Jian-Xiao Jiang and Shen Yang and Fei Qin and Ze-Kun Li and Xin Cong and Bin Xu and Lei Hou and Man-Li Li and Juan-Zi Li and Hui-Qin Liu and Yu Zhang and Zhi-Yuan Liu and Mao-Song Sun} }

FAQ

## Frequently Asked Questions

### What is OpenMAIC?

OpenMAIC (Open Multi-Agent Interactive Classroom) is an open-source AI platform developed by Tsinghua University that transforms any topic or document into an immersive, interactive classroom experience. It uses multi-agent orchestration with LLM-driven AI teachers and classmates to deliver personalized, engaging lessons.

### Who developed OpenMAIC?

OpenMAIC was developed by the THU-MAIC team at Tsinghua University. The project has been validated with over 700 students across more than two years of real-world deployment, and the research has been published in the Journal of Computer Science and Technology (JCST 2026).

### How does the lesson generation pipeline work?

OpenMAIC uses a two-stage generation pipeline. First, the AI analyzes your input — a topic description or uploaded document — and generates a structured lesson outline. Then, each outline item is transformed into rich scenes: slides with voice narration, quizzes with grading rubrics, interactive HTML simulations, or project-based learning activities.

### What LLM providers are supported?

OpenMAIC supports multiple LLM providers including OpenAI, Anthropic, Google Gemini, DeepSeek, and any OpenAI-compatible API. The recommended model is Gemini 3 Flash for the best balance of quality and speed, with Gemini 3.1 Pro available for highest quality output.

### Is OpenMAIC free to use?

Yes. OpenMAIC is open-source and released under the AGPL-3.0 license. You can freely use, modify, and deploy it. For commercial licensing inquiries, contact the team at [[email protected]](/cdn-cgi/l/email-protection).

### Can I use OpenMAIC from messaging apps?

Yes. Through OpenClaw integration, you can generate and view interactive classrooms directly from Feishu, Slack, Discord, Telegram, WhatsApp, and 20+ other messaging platforms — without ever touching a terminal. Install with: `clawhub install openmaic`.

Explore

## Dive Deeper into OpenMAIC

Learn more about each capability of the OpenMAIC platform through our in-depth guides and feature pages. 

### [AI Interactive Classroom](/openmaic-ai-interactive-classroom.html)

Experience immersive lessons where AI teachers deliver lectures with voice narration, spotlight effects, and real-time whiteboard interactions in a fully interactive environment.

[Learn more →](/openmaic-ai-interactive-classroom.html)

### [Multi-Agent Learning](/openmaic-multi-agent-learning.html)

Discover how multiple AI agents collaborate as teachers and classmates, initiating discussions, debates, and group problem-solving to simulate real classroom dynamics.

[Learn more →](/openmaic-multi-agent-learning.html)

### [Online Course Generator](/openmaic-online-course-generator.html)

Generate complete interactive courses from any topic description or uploaded document. The AI builds structured lessons with slides, quizzes, and simulations in minutes.

[Learn more →](/openmaic-online-course-generator.html)

### [AI Teacher Assistant](/openmaic-ai-teacher-assistant.html)

Meet the intelligent virtual teaching agent — with text-to-speech narration, real-time Q&A capability, and AI-powered grading that provides instant personalized feedback.

[Learn more →](/openmaic-ai-teacher-assistant.html)

### [Interactive Simulations](/openmaic-interactive-simulation.html)

Explore AI-generated hands-on experiments — physics simulators, algorithm visualizations, flowcharts, and more — all running as self-contained HTML in the browser.

[Learn more →](/openmaic-interactive-simulation.html)

### [Project-Based Learning](/openmaic-project-based-learning.html)

Engage in structured AI-driven projects with role selection, milestone tracking, and collaborative deliverables — designed for deeper applied understanding.

[Learn more →](/openmaic-project-based-learning.html)

Step-by-step guide to installing, configuring, and running OpenMAIC — from cloning the repository to deploying on Vercel or Docker in production.

[Learn more →](/openmaic-tutorial-getting-started.html)

### [PPTX & HTML Export](/openmaic-pptx-export-tool.html)

Export AI-generated lessons to fully editable PowerPoint slides with images, charts, and LaTeX formulas, or as self-contained interactive HTML pages.

[Learn more →](/openmaic-pptx-export-tool.html)

### [Open Source Education](/openmaic-open-source-education.html)

Learn about OpenMAIC's open-source philosophy under the AGPL-3.0 license, community contributions, and the vision for accessible AI-powered education worldwide.

[Learn more →](/openmaic-open-source-education.html)
