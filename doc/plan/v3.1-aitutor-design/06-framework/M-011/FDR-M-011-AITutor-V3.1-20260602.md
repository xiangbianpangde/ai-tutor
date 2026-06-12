# 框架决策记录（FDR） — M-011 FSRS 调度 — AITutor V3.1

> 负责模块: M-011
> 决策数: 3 条
> 全部状态: 已接受

---

## FDR-M011-001

- **决策编号**: FDR-M011-001
- **决策标题**: FSRSScheduler 采用 Singleton 单例封装 py-fsrs
- **决策状态**: 已接受
- **决策内容**: 全进程唯一 FSRSScheduler 实例持有 py-fsrs.Scheduler，对外仅暴露 `get_default_scheduler()` 工厂方法
- **决策理由**:
  1. py-fsrs 内部存在算法状态（desired_retention、fuzzing 参数），全进程共享避免卡片参数漂移
  2. M-009 教学编排高并发调用 schedule_card，单例可避免重复创建 Scheduler
  3. py-fsrs 1.0+ 文档明确建议 Singleton 使用
- **拒绝的替代方案**:
  - 方案A: 每次调用 new FSRSScheduler() — 拒绝理由：py-fsrs 内部状态会漂移（多实例间 desired_retention 同步困难）
  - 方案B: 线程局部单例（thread-local）— 拒绝理由：M-011 调用方多线程并发，thread-local 反而引入隔离问题
- **影响范围**:
  - 文件: `scheduler.py`
  - 接口: API-M011-001
  - 测试: `test_singleton_returns_same_instance` / `test_singleton_thread_safety`
- **相关FDR**: N/A
- **来源标注**: [DD-001:MD-M-011 Singleton 设计] + [DD-M推断:依据=py-fsrs 官方 Singleton 最佳实践]

---

## FDR-M011-002

- **决策编号**: FDR-M011-002
- **决策标题**: AgainThrottle 节流窗口 300s（5min/卡）
- **决策状态**: 已接受
- **决策内容**: 节流窗口硬编码 300s（5min/卡），告警阈值 3 次
- **决策理由**:
  1. EX-018 明确要求 5min/卡 节流 + >3 计数告警
  2. SEC-013 数据完整性边界要求 again 频率受控
  3. 5min 窗口与 FSRS 算法「短期记忆」时段吻合
- **拒绝的替代方案**:
  - 方案A: 可配置窗口（env 注入）— 拒绝理由：EX-018 硬约束，不应允许业务方调整
  - 方案B: 滑动窗口（精确 5min 内 N 次）— 拒绝理由：复杂度高，收益低；固定窗口足够
- **影响范围**:
  - 文件: `throttle.py`
  - 接口: API-M011-002
  - 测试: `test_is_throttled_within_5min` / `test_is_throttled_expires_after_cooldown`
- **相关FDR**: N/A
- **来源标注**: [DD-001:EX-018] + [DD-001:SEC-013]

---

## FDR-M011-003

- **决策编号**: FDR-M011-003
- **决策标题**: 数据损坏 E01101 走"重建卡 + ERROR 日志"策略
- **决策状态**: 已接受
- **决策内容**: grade 越界 / card 字段为 None 时抛出 FSRSCorruptedError，由调用方决定是否重建卡；同时 ERROR 日志写入
- **决策理由**:
  1. MD-M-011 明确要求 E01101 触发时重建卡 + ERROR 日志
  2. 异常路径与正常路径严格分离（拒绝默默修正）
  3. ERROR 日志便于溯源（trace_id + card_id 写入）
- **拒绝的替代方案**:
  - 方案A: 自动修正 grade（如 5→4）— 拒绝理由：违反 FSRS 算法语义，引入不可预测行为
  - 方案B: 静默丢弃（不抛异常）— 拒绝理由：违反 M-011 异常处理规范
- **影响范围**:
  - 文件: `scheduler.py`
  - 接口: API-M011-001
  - 测试: `test_schedule_card_grade_out_of_range_raises`
- **相关FDR**: N/A
- **来源标注**: [DD-001:MD-M-011 异常处理] + [DD-001:EX-018]

---

来源标注：[DD-001:MD-M-011/EX-018/SEC-013] + [DD-M推断:依据=soul 3.7 FDR 模板]
