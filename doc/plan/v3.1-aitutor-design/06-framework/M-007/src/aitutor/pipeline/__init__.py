"""aitutor.pipeline - Pipeline 调度模块

> 对应模块: M-007
> 关联接口: IC-002 (学习回合)、IC-003 (RAG 检索)
> 关联选型: TS-001 Python / TS-002 FastAPI
> 设计模式: Pipeline + Strategy
> 来源标注: [DD-001:FS-M-007/MD-M-007/IC-002/IC-003]

[文件职责]  Pipeline 调度模块入口，导出公共接口
[所属模块]  M-007（Pipeline 调度）
[关联设计规范]  FS-M-007 / MD-M-007 / IC-002 / IC-003
[功能描述]
  功能1: 导出 PipelineOrchestrator / PipelineState / FallbackStrategy 等公共类
  功能2: 提供 5 阶段管线的统一入口
  功能3: 集中管理兜底策略（10% LLM 兜底）
[输入输出]
  输入: 无（仅做模块初始化）
  输出: 对外暴露的类与函数符号
[依赖关系]
  依赖文件: ./orchestrator.py、./state.py、./fallback.py、./stages/*
  被依赖文件: aitutor.api.v1.turn（M-002 调用）、aitutor.teaching.orchestrator（M-009 调用）
[注意事项]
  注意1: 禁止在本文件实现业务逻辑，仅做 re-export
  注意2: 公共 API 必须显式列出，禁止通配符导出
[代码风格]  CS-AITutor-V3.1-20260602（4 空格缩进 / Google Docstring / 双引号）
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-007 - 初始版本，含 5 阶段 + FSM + 兜底注释骨架
[作者]  DD-M-007-20260602
[来源标注]  [DD-001:FS-M-007]
"""
# [DD-001:FS-M-007] Pipeline 调度模块公开符号集中处，便于上层按需 import

# [DD-M推断:依据=FS-M-007 M-007 段] 核心调度类
# [DD-M推断:依据=MD-M-007 类设计 PipelineOrchestrator 行]
# [DD-M推断:依据=MD-M-007 类设计 PipelineState 行]
# [DD-M推断:依据=MD-M-007 异常处理 E00702 行]
# [DD-M推断:依据=MD-M-007 状态机段 INIT→...→DONE]
# [DD-M推断:依据=MD-M-007 类设计 5 个 Stage 行]
# [DD-M推断:依据=MD-M-007 子模块拆分 sm007-preprocess/retrieve/rerank/llm/postprocess]
