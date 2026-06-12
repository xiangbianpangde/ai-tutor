"""aitutor.pipeline.stages - 5 阶段子包

> 对应模块: M-007
> 关联接口: IC-002（学习回合）/ IC-003（RAG 检索）
> 关联选型: TS-001 Python
> 来源标注: [DD-001:FS-M-007/MD-M-007/IC-002/IC-003]

[文件职责]  Pipeline 5 阶段子包入口
[所属模块]  M-007（Pipeline 调度）
[关联设计规范]  MD-M-007 子模块拆分 sm007-preprocess/retrieve/rerank/llm/postprocess
[功能描述]
  功能1: 导出 5 个 Stage 类
  功能2: 提供 Stage 抽象基类
[输入输出]
  输入: 无
  输出: 5 个 Stage 类的符号
[依赖关系]
  依赖文件: ./preprocess.py、./retrieve.py、./rerank.py、./llm.py、./postprocess.py
  被依赖文件: ../orchestrator.py
[注意事项]
  注意1: 所有 Stage 必须实现 abstract run(input) 方法
  注意2: 禁止在本文件实现业务逻辑
[代码风格]  CS-AITutor-V3.1-20260602
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-007 - 初始版本
[作者]  DD-M-007-20260602
[来源标注]  [DD-001:FS-M-007 stages/ 段]
"""
# [DD-001:FS-M-007 M-007 段] 5 阶段独立子模块
# [DD-001:MD-M-007 子模块拆分] sm007-{preprocess,retrieve,rerank,llm,postprocess}
# [DD-M推断:依据=Pipeline 模式] Stage 抽象基类 + 5 个实现
