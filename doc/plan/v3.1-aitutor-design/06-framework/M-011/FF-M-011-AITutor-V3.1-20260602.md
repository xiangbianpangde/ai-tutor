# 文件框架结构 — M-011 FSRS 调度（Singleton） — AITutor V3.1

> 负责模块: M-011（FSRS 调度）
> 关联上游: [DD-001:MD-M-011/FS-M-011/CS-AITutor] + [DD-001:TS-007]
> 设计模式: Singleton（FSRSScheduler 单例约束：算法状态必须全进程共享，避免卡片参数漂移）
> 框架轮次: 1 / 4
> 模块边界: 仅 M-011 内文件，跨模块操作数 = 0（D7=100）

---

## 1. 文件框架

```
src/aitutor/fsrs/
├── __init__.py          ← [职责: 模块初始化，导出公共接口 FSRSScheduler/AgainThrottle]
├── scheduler.py         ← [职责: FSRS 算法封装（py-fsrs Singleton），含 schedule_card/update_card]
│   - [类注释: FSRSScheduler（Singleton）]
│   - [类注释: FSRSCard（py-fsrs Card 数据载体）]
│   - [函数注释: schedule_card(card: FSRSCard, grade: int) -> FSRSCard]
│   - [函数注释: update_card(card: FSRSCard, grade: int) -> FSRSCard]
│   - [函数注释: get_due_cards(cards: List[FSRSCard], now: datetime) -> List[FSRSCard]]
│   - [函数注释: get_default_scheduler() -> FSRSScheduler]
└── throttle.py          ← [职责: Again 频繁触发的 5min/卡 节流，节流审计写入]
    - [类注释: AgainThrottle（基于时间窗口 + 计数）】
    - [类注释: ThrottleRecord（节流记录：card_id / last_again_ts / count）】
    - [函数注释: is_throttled(card_id: str) -> bool]
    - [函数注释: record_again(card_id: str) -> None]
    - [函数注释: get_throttle_stats() -> ThrottleStats]
    - [函数注释: reset_throttle(card_id: str) -> None]

tests/unit/test_fsrs/
├── __init__.py          ← [职责: 测试包初始化]
├── test_scheduler.py    ← [职责: FSRSScheduler 单例 + schedule/update/get_due 测试]
│   - [场景1: 正常 schedule] [断言: next_due 提前] [Mock: py-fsrs.Scheduler]
│   - [场景2: Singleton 校验] [断言: 多次 get_default_scheduler 返回同一实例] [Mock: 无]
│   - [场景3: 数据损坏] [断言: 抛出 E01101 + 重建卡] [Mock: 损坏 Card]
│   - [场景4: grade 边界 0/5] [断言: schedule 返回合规 card] [Mock: 无]
│   - [场景5: get_due_cards 时区] [断言: 过滤 next_due<=now 的卡] [Mock: Clock fixture]
├── test_throttle.py     ← [职责: AgainThrottle 节流 + 计数 + 审计日志]
│   - [场景1: 5min 内重复] [断言: 第二次 is_throttled=True] [Mock: Clock fixture]
│   - [场景2: 5min 后允许] [断言: 第二次 is_throttled=False] [Mock: Clock fixture]
│   - [场景3: 计数>3] [断言: 写 audit_log + 仍可节流] [Mock: audit_log]
│   - [场景4: 多卡隔离] [断言: 不同 card_id 互不影响] [Mock: 无]
│   - [场景5: reset_throttle] [断言: 清除记录] [Mock: 无]
```

---

## 2. 文件间依赖关系

```
tests/test_fsrs/test_scheduler.py
    ↓ (调用)
aitutor.fsrs.scheduler (FSRSScheduler + schedule_card + update_card)
    ↓ (内部使用)
py-fsrs (TS-007, 第三方库)

aitutor.fsrs.throttle (AgainThrottle)
    ↓ (依赖)
aitutor.shared.types (ThrottleRecord)
    ↓
aitutor.monitor.logger (structlog 写 audit_log)

外部调用方（来自其他模块，但 M-011 不感知）:
  M-009 教学编排 → M-011 (schedule_card / is_throttled)
  M-013 长期记忆 → M-011 (节流 audit_log 引用)
```

**依赖图（仅 M-011 内部）**：
```
scheduler.py → (py-fsrs 第三方, Singleton 自封装)
throttle.py  → (datetime 内置, structlog 日志, shared.types 跨模块只读)
```
**禁止依赖**（R26/R28）:
- scheduler.py / throttle.py 禁止反向依赖 M-009/M-013 模块文件
- 禁止 M-011 内部循环依赖

---

## 3. 文件结构 5 项合规检查（4.7 客观清单）

| 检查项 | 检查标准 | 通过条件 | 结果 |
|--------|---------|---------|------|
| 目录层级 | 目录层级≥2层 | `src/aitutor/fsrs/` ≥ 2层 | 通过 |
| 文件命名 | snake_case | `scheduler.py`/`throttle.py`/`test_scheduler.py` 全合规 | 通过 |
| 文件职责 | 每个文件单一职责 | scheduler=算法封装 / throttle=节流审计 / 互不重叠 | 通过 |
| 依赖关系 | 无循环依赖 | scheduler↔throttle 无相互调用, 仅 M-011 内部单向 | 通过 |
| 最佳实践 | Singleton + 测试目录 | Singleton 注解 + `tests/unit/test_fsrs/` 命名空间 | 通过 |

**5/5 全部通过 → 合规度 = 高**

---

## 4. 来源标注

| 文件 | 来源 |
|------|------|
| `fsrs/__init__.py` | [DD-001:FS-M-011] + [DD-M推断:依据=M-004/M-011 公共接口导出范式] |
| `fsrs/scheduler.py` | [DD-001:MD-M-011/FS-M-011] + [DD-001:TS-007 py-fsrs] |
| `fsrs/throttle.py` | [DD-001:MD-M-011/EX-018] + [DD-001:SEC-013] |
| `tests/test_fsrs/test_scheduler.py` | [DD-001:MD-M-011 测试策略 10 用例] + [DD-M推断:依据=CS 测试规范] |
| `tests/test_fsrs/test_throttle.py` | [DD-001:EX-018] + [DD-001:MD-M-011 测试策略] |

---

## 5. 框架决策记录摘要（详见 FDR 文档）

| FDR 编号 | 决策标题 | 状态 |
|---------|---------|------|
| FDR-M011-001 | FSRSScheduler 采用 Singleton 单例封装 py-fsrs | 已接受 |
| FDR-M011-002 | AgainThrottle 节流窗口 300s（5min/卡）| 已接受 |
| FDR-M011-003 | 数据损坏 E01101 走"重建卡 + ERROR 日志"策略 | 已接受 |

---

[DD-001:DDI=0.96 接收通过] + [DD-M推断:依据=soul 6.1 命名规范]
