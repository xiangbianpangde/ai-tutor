# 接口注释清单 — M-011 FSRS 调度 — AITutor V3.1

> 负责模块: M-011（FSRS 调度）
> 关联上游: [DD-001:IC-002] + [DD-001:MD-M-011]
> 接口数: 2（API-M011-001 schedule_card / API-M011-002 is_throttled）
> 验收: 全部通过 4.12 验收标准

---

## API-M011-001 schedule_card

- **接口编号**: API-M011-001
- **关联契约**: IC-002（学习回合 grade 参数）
- **来源标注**: [DD-001:MD-M-011] + [DD-001:IC-002]
- **实现文件**: `src/aitutor/fsrs/scheduler.py`
- **类**: `FSRSScheduler`
- **函数签名注释**:

  ```python
  def schedule_card(
      card: FSRSCard,                          # 待调度卡片（含 py-fsrs Card）
      grade: int,                              # 评分 1=Again, 2=Hard, 3=Good, 4=Easy [校验: 1<=grade<=4]
      now: Optional[datetime.datetime] = None, # 调度基准时间（默认 utcnow）
  ) -> FSRSCard:
      """根据评分调度卡片的下次到期时间。

      Args:
          card: 待调度的 FSRS 卡片（必须已构造 py_card 字段）
          grade: 评分 1=Again / 2=Hard / 3=Good / 4=Easy
          now: 基准时间（UTC），默认 datetime.utcnow()

      Returns:
          FSRSCard: 调度后的新卡片（next_due 字段已更新，review_count+1）

      Raises:
          FSRSCorruptedError: grade 越界（<1 或 >4）/ card 字段为 None（E01101）
          ValueError: card_id 非法（非 UUID 格式）

      Example:
          >>> card = FSRSCard.from_dict({"card_id": "...", "py_card": ...})
          >>> new_card = scheduler.schedule_card(card, grade=3)
          >>> new_card.next_due > datetime.utcnow()
          True

      Note:
          - Singleton 工厂方法 get_default_scheduler() 获取实例
          - 性能约束 ≤10ms
          - 不修改原 card 对象（返回新对象）
      """
  ```
- **参数说明**:
  - 参数1: `card: FSRSCard` 必填 卡片实体
  - 参数2: `grade: int` 必填 评分 1~4
  - 参数3: `now: Optional[datetime.datetime]` 可选 默认 `datetime.utcnow()`
- **返回值说明**:
  - 类型: `FSRSCard`
  - 描述: 调度后的新卡片
  - 特殊值: grade 越界时抛出 FSRSCorruptedError
- **错误码说明**:
  - 错误码1: `E01101` 含义: 卡片数据损坏 触发: grade 越界 / card 字段为 None

---

## API-M011-002 is_throttled

- **接口编号**: API-M011-002
- **关联契约**: IC-002（学习回合 Again 节流保护）
- **来源标注**: [DD-001:EX-018] + [DD-001:MD-M-011]
- **实现文件**: `src/aitutor/fsrs/throttle.py`
- **类**: `AgainThrottle`
- **函数签名注释**:

  ```python
  def is_throttled(
      card_id: str,                             # 卡片 ID（UUIDv4）
      now: Optional[datetime.datetime] = None,  # 基准时间（默认 utcnow）
  ) -> bool:
      """判断卡片是否处于节流窗口。

      Args:
          card_id: 卡片唯一 ID
          now: 基准时间（UTC），默认 datetime.utcnow()

      Returns:
          bool: True=在节流窗口（应拒绝处理）/ False=不在窗口

      Raises:
          无（不抛异常，查询语义）

      Example:
          >>> throttle = AgainThrottle()
          >>> throttle.record_again("card-uuid-1")
          >>> throttle.is_throttled("card-uuid-1")
          True  # 5min 内
          >>> # 5min 后
          >>> throttle.is_throttled("card-uuid-1")
          False

      Note:
          - 节流窗口 300s（5min/卡）来自 EX-018 硬约束
          - 进程内内存持有（不持久化）
      """
  ```
- **参数说明**:
  - 参数1: `card_id: str` 必填 UUIDv4
  - 参数2: `now: Optional[datetime.datetime]` 可选
- **返回值说明**:
  - 类型: `bool`
  - 描述: True=节流中, False=可处理
  - 特殊值: 卡片无记录时返回 False
- **错误码说明**:
  - 错误码1: `E01102` 含义: 节流触发（仅日志，调用方不感知异常）

---

## 接口清单验收（4.12）

| 接口编号 | 入参完整 | 出参完整 | 错误码覆盖 | 前置后置 | 幂等性 | 性能约束 | 验收 |
|---------|---------|---------|-----------|---------|--------|---------|------|
| API-M011-001 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| API-M011-002 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |

**2/2 全部通过验收**

来源标注：[DD-001:IC-002/MD-M-011/EX-018] + [DD-M推断:依据=soul 3.6 接口注释模板]
