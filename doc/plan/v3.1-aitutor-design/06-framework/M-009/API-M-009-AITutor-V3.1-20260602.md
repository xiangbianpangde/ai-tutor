# API-M-009 接口注释清单 — AITutor V3.1

> [模块编号] M-009
> [负责实例] DD-M-009
> [来源标注] [DD-001:IC-002/IC-007] + [DD-M推断:依据=接口契约注释化]

---

## API-M-009-001 教学下一步（IC-002 学习回合子接口）

[接口编号] API-M-009-001
[关联契约] IC-002 学习回合（来自 DD-001）
[实现文件] src/aitutor/teaching/orchestrator.py
[函数签名注释]
  ```python
  def next_step(self, user_id: str, session_id: str) -> "NextStep":
      """
      计算下一步教学动作。

      Args:
          user_id: 用户 ID，32hex 字符串，强校验。
          session_id: 会话 ID，UUIDv4 格式。

      Returns:
          NextStep: 包含 next_action、next_state、expected_duration_s 字段。

      Raises:
          TeachingFSMStuckError: FSM 无合法转换（E00902）。
          SessionNotFoundError: session 不存在（E00401）。

      Example:
          >>> result = orch.next_step("u_abc123", "s_def456")
          >>> result.next_state
          'LEARN'
      """
  ```
[参数说明]
  参数1: user_id str 必填 32hex 字符串，强校验
  参数2: session_id str 必填 UUIDv4 格式
[返回值说明] NextStep 对象，含 next_action/next_state/expected_duration_s
[错误码说明]
  E00902: FSM 卡死 → LLM 兜底 + audit_log
  E00401: session 不存在 → 404
[来源标注] [DD-001:IC-002/MD-009]

---

## API-M-009-002 动作分发（IC-002 通用动作）

[接口编号] API-M-009-002
[关联契约] IC-002 学习回合
[实现文件] src/aitutor/teaching/orchestrator.py → dispatcher.py
[函数签名注释]
  ```python
  def dispatch_action(self, action: str, context: "TeachingContext") -> "ActionResult":
      """
      通用动作分发（Mediator 入口）。

      Args:
          action: 动作名（白名单：feynman/fsrs/stage_change/idle）。
          context: 教学上下文，含 user_id/session_id 等。

      Returns:
          ActionResult: success/payload/next_state/error_code/trace_id。

      Raises:
          UnknownActionError: 动作未注册且无 fallback。
      """
  ```
[参数说明]
  参数1: action str 必填 白名单
  参数2: context TeachingContext 必填
[返回值说明] ActionResult
[错误码说明]
  E00901: LLM 评分失败
  E00902: FSM 卡死
  E00903: FSRS 版本低
[来源标注] [DD-001:IC-002] + [DD-M推断:依据=Mediator 通用接口]

---

## API-M-009-003 费曼评分（IC-002 费曼段）

[接口编号] API-M-009-003
[关联契约] IC-002 学习回合
[实现文件] src/aitutor/teaching/orchestrator.py → feynman/scorer.py (M-010)
[函数签名注释]
  ```python
  def teach_feynman(self, question: str) -> "FeynmanResult":
      """
      教学侧费曼评分封装。

      Args:
          question: 长度 [1, 2000] 费曼问题。

      Returns:
          FeynmanResult: score (0-5)/feedback/gaps。

      Raises:
          FeynmanScoreError: LLM 评分失败（E01001/E01002/E00901）。
      """
  ```
[参数说明]
  参数1: question str 必填 [1, 2000]
[返回值说明] FeynmanResult
[错误码说明]
  E01001: LLM 不可用 → 0 + WARN
  E01002: 解析失败 → 重试 1 次
  E00901: 兜底 → FSM 10%
[来源标注] [DD-001:IC-002/MD-009] + [DD-M推断:依据=跨模块委托]

---

## API-M-009-004 FSRS 调度（IC-002 FSRS 段）

[接口编号] API-M-009-004
[关联契约] IC-002 学习回合
[实现文件] src/aitutor/teaching/orchestrator.py → fsrs/scheduler.py (M-011)
[函数签名注释]
  ```python
  def schedule_fsrs(self, card_id: str, grade: int) -> "FSRSCard":
      """
      FSRS 间隔重复调度封装。

      Args:
          card_id: FSRS 卡片 ID。
          grade: 评分，0=Again, 1=Hard, 2=Good, 3=Easy。

      Returns:
          FSRSCard: due/stability/difficulty/reps。
      """
  ```
[参数说明]
  参数1: card_id str 必填
  参数2: grade int 必填 [0, 3]
[返回值说明] FSRSCard
[错误码说明]
  E00903: FSRS 版本低 → 升级提示
  E01101: FSRS 数据损坏 → 重建卡
  E01102: 节流触发 → 计数 + 拒绝
[来源标注] [DD-001:IC-002/MD-009] + [DD-M推断:依据=py-fsrs 1.0 接口]

---

## API-M-009-005 FSM 推进

[接口编号] API-M-009-005
[关联契约] IC-002（FSM 子能力）
[实现文件] src/aitutor/teaching/state_machine.py
[函数签名注释]
  ```python
  def transition(self, event: TeachingEvent) -> TeachingState:
      """
      推进教学 FSM 到下一态。

      Args:
          event: 触发事件。

      Returns:
          TeachingState: 推进后的状态。

      Raises:
          TeachingFSMStuckError: 无合法转换（E00902）。
      """
  ```
[参数说明]
  参数1: event TeachingEvent 必填
[返回值说明] TeachingState
[错误码说明] E00902
[来源标注] [DD-001:MD-009] + [DD-M推断:依据=FSM 标准接口]

---

## API-M-009-006 Mediator 异步分发

[接口编号] API-M-009-006
[关联契约] IC-002
[实现文件] src/aitutor/teaching/dispatcher.py
[函数签名注释]
  ```python
  async def dispatch(self, context: TeachingContext) -> ActionResult:
      """
      异步分派 context 到对应 handler。

      Args:
          context: 教学上下文。

      Returns:
          ActionResult: handler 返回值。
      """
  ```
[参数说明]
  参数1: context TeachingContext 必填
[返回值说明] ActionResult
[错误码说明]
  E00901: Feynman 失败
  E00903: FSRS 版本
  UnknownActionError: 无 fallback
[来源标注] [DD-001:IC-002] + [DD-M推断:依据=Mediator 异步分发]

---

## 接口契约覆盖统计

| 接口编号 | IC 关联 | 函数签名 | 参数 | 返回值 | 错误码 | 状态 |
|---------|---------|---------|------|--------|--------|------|
| API-M-009-001 | IC-002 | ✅ | ✅ | ✅ | ✅ | 完整 |
| API-M-009-002 | IC-002 | ✅ | ✅ | ✅ | ✅ | 完整 |
| API-M-009-003 | IC-002 | ✅ | ✅ | ✅ | ✅ | 完整 |
| API-M-009-004 | IC-002 | ✅ | ✅ | ✅ | ✅ | 完整 |
| API-M-009-005 | IC-002 | ✅ | ✅ | ✅ | ✅ | 完整 |
| API-M-009-006 | IC-002 | ✅ | ✅ | ✅ | ✅ | 完整 |

**接口注释覆盖率：6/6 = 100%**

## 来源标注

[DD-001:IC-002] + [DD-M推断:依据=接口契约注释化完整度 D4≥80]
