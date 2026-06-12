# 接口注释清单 — M-012 阶段校准

> 模块编号: M-012
> 关联契约: 通过 M-009 教学编排（IC-002 学习回合）调用，无独立 IC-NNN
> 来源标注: [DD-001:MD-012] + [DD-M推断:依据=M-012 模块细化方案]

---

## API-M012-001 evaluate_stage

| 字段 | 内容 |
|------|------|
| 接口编号 | API-M012-001 |
| 关联契约 | 通过 IC-002 学习回合（经 M-009 orchestrator 转发） |
| 实现文件 | src/aitutor/stage/evaluator.py |
| 函数签名 | `def evaluate_stage(performance: Performance) -> int` |
| 参数说明 | performance: Performance（必填，用户表现数据） |
| 返回值说明 | int 目标档位 [1, 5]；数据不足时返回 current_stage |
| 错误码 | E01201 数据不足 |
| 性能约束 | O(7) 默认窗口 |
| 并发安全 | 是 |
| 幂等性 | 是 |
| 来源标注 | [DD-001:MD-012] |

## API-M012-002 transition_stage

| 字段 | 内容 |
|------|------|
| 接口编号 | API-M012-002 |
| 关联契约 | 通过 IC-002 学习回合（经 M-009 orchestrator 转发） |
| 实现文件 | src/aitutor/stage/transition.py |
| 函数签名 | `def transition_stage(current: int, new: int) -> bool` |
| 参数说明 | current: int（必填，当前档位）/ new: int（必填，目标档位） |
| 返回值说明 | bool True=允许转换 / False=拒绝 |
| 错误码 | E01202 越界（自动钳制） |
| 性能约束 | O(1) |
| 并发安全 | 是 |
| 幂等性 | 是 |
| 来源标注 | [DD-001:MD-012] |

## API-M012-003 StageEvaluator.evaluate

| 字段 | 内容 |
|------|------|
| 接口编号 | API-M012-003 |
| 关联契约 | 同 API-M012-001 |
| 实现文件 | src/aitutor/stage/evaluator.py |
| 函数签名 | `def evaluate(self, performance: Performance) -> int` |
| 参数说明 | performance: Performance |
| 返回值说明 | int 目标档位 |
| 错误码 | E01201 数据不足 |
| 性能约束 | O(window) |
| 并发安全 | 是 |
| 幂等性 | 是 |
| 来源标注 | [DD-001:MD-012] |

## API-M012-004 StageTransition.can_up

| 字段 | 内容 |
|------|------|
| 接口编号 | API-M012-004 |
| 关联契约 | 通过 M-009 调用 |
| 实现文件 | src/aitutor/stage/transition.py |
| 函数签名 | `def can_up(self, current: int) -> bool` |
| 参数说明 | current: int 当前档位 |
| 返回值说明 | bool True=可升 / False=已在最高 |
| 错误码 | 无 |
| 性能约束 | O(1) |
| 并发安全 | 是 |
| 幂等性 | 是 |
| 来源标注 | [DD-001:MD-012] |

## API-M012-005 StageTransition.can_down

| 字段 | 内容 |
|------|------|
| 接口编号 | API-M012-005 |
| 关联契约 | 通过 M-009 调用 |
| 实现文件 | src/aitutor/stage/transition.py |
| 函数签名 | `def can_down(self, current: int) -> bool` |
| 参数说明 | current: int 当前档位 |
| 返回值说明 | bool True=可降 / False=已在最低 |
| 错误码 | 无 |
| 性能约束 | O(1) |
| 并发安全 | 是 |
| 幂等性 | 是 |
| 来源标注 | [DD-001:MD-012] |

## API-M012-006 StageTransition.clamp

| 字段 | 内容 |
|------|------|
| 接口编号 | API-M012-006 |
| 关联契约 | 通过 M-009 / M-012 内部调用 |
| 实现文件 | src/aitutor/stage/transition.py |
| 函数签名 | `@staticmethod def clamp(stage: int) -> int` |
| 参数说明 | stage: int 待钳制档位 |
| 返回值说明 | int 钳制后档位 [1, 5] |
| 错误码 | E01202 越界（仅日志 WARN） |
| 性能约束 | O(1) |
| 并发安全 | 是 |
| 幂等性 | 是 |
| 来源标注 | [DD-001:MD-012] + [DD-M推断:依据=E01202 钳制实现] |

---

## 来源标注汇总

[DD-001:MD-012] + [DD-M推断:依据=M-012 模块细化方案 + 6 个公开 API 的签名/参数/返回/错误码/并发/幂等 6 维注释]
