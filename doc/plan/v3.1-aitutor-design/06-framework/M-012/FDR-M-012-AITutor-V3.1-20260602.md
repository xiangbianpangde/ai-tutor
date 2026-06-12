# 框架决策记录（FDR） — M-012 阶段校准

> 模块编号: M-012
> 来源标注: [DD-001:FS-012/MD-012] + [DD-M推断:依据=Strategy 模式最佳实践]

---

## FDR-M012-001 拆分 evaluator 与 transition 两个文件

- **决策编号**: FDR-M012-001
- **决策标题**: M-012 拆分为 evaluator.py + transition.py 两个文件
- **决策状态**: 已接受
- **决策内容**: 阶段校准模块按职责拆分为评估（evaluator.py）和转换（transition.py）两个文件
- **决策理由**:
  - 1) 评估涉及滑动窗口/聚合/hysteresis 判定，逻辑复杂；转换仅涉及 can_up/can_down/clamp，逻辑简单
  - 2) 单一职责原则（SRP）：评估与转换的变更频率不同（评估依赖表现数据，转换依赖档位规则）
  - 3) 单一文件若合并将超过 200 行且类数 > 3，违反 soul 4.7 文件职责检查
- **拒绝的替代方案**:
  - 方案A: 单文件 stage.py（包含所有逻辑）— 拒绝理由: 违反单一职责，函数将 > 20 个
  - 方案B: 拆分为 strategy_evaluate/strategy_transition — 拒绝理由: Python 工程中过度命名空间，目录层级 4 层过深
- **影响范围**: src/aitutor/stage/ 全部文件
- **相关FDR**: 无
- **来源标注**: [DD-001:FS-012] + [DD-M推断:依据=soul 4.7 文件职责单一性]

## FDR-M012-002 滞回窗口默认 2 天（hysteresis=2d）

- **决策编号**: FDR-M012-002
- **决策标题**: StageEvaluator 默认 hysteresis=2d、window=7d
- **决策状态**: 已接受
- **决策内容**: StageEvaluator 默认参数 window=7、hysteresis=2
- **决策理由**: MD-012 明确声明 window=7d、hysteresis=2d，直接采用 DD-001 规范
- **拒绝的替代方案**:
  - 方案A: window=14 / hysteresis=3 — 拒绝理由: 与 MD-012 规范不一致
  - 方案B: 暴露为可配置（环境变量）— 拒绝理由: 增加复杂度且无明确需求
- **影响范围**: StageEvaluator.__init__ / evaluate_stage 顶层函数
- **相关FDR**: 无
- **来源标注**: [DD-001:MD-012]

## FDR-M012-003 表现聚合权重 accuracy 0.5 / speed 0.2 / retention 0.3

- **决策编号**: FDR-M012-003
- **决策标题**: Performance.to_score() 权重分配
- **决策状态**: 已接受（标注 DD-M 推断）
- **决策内容**: 综合得分 = accuracy*0.5 + speed_score*0.2 + retention*0.3
- **决策理由**: MD-012 未明确权重，按 M-009 教学编排对费曼评分/FSRS 的隐含权重推断（准确率为核心学习指标，响应速度为辅助）
- **拒绝的替代方案**:
  - 方案A: 等权重 1/3 — 拒绝理由: 教学场景中 accuracy 应主导
  - 方案B: 仅用 accuracy — 拒绝理由: 单一指标，无法反映学习者多维能力
- **影响范围**: Performance.to_score() / StageEvaluator._score_to_stage()
- **相关FDR**: 无
- **来源标注**: [DD-M推断:依据=MD-012 隐含权重 + 教学领域常识]

## FDR-M012-004 转换跨度限制单步 1 档

- **决策编号**: FDR-M012-004
- **决策标题**: transition_stage 单步跨度 ≤ 1
- **决策状态**: 已接受（标注 DD-M 推断）
- **决策内容**: transition_stage 拒绝跨度 > 1 的转换（如 3→5、3→1）
- **决策理由**:
  - 1) 防止档位跳跃带来的体验断层（用户无法适应档位内容）
  - 2) MD-012 仅声明 can_up/can_down，隐含单步升降
  - 3) hysteresis 评估本就是渐进式策略
- **拒绝的替代方案**:
  - 方案A: 允许任意跨度 — 拒绝理由: 与 hysteresis 防抖冲突
  - 方案B: 跨度可配置 — 拒绝理由: 引入未声明的可配置参数
- **影响范围**: transition_stage() / StageTransition 类
- **相关FDR**: 无
- **来源标注**: [DD-M推断:依据=MD-012 can_up/can_down 隐含单步]

## FDR-M012-005 测试用例数 15（evaluator 9 + transition 6）

- **决策编号**: FDR-M012-005
- **决策标题**: M-012 测试用例数对齐 MD-012 策略
- **决策状态**: 已接受
- **决策内容**: evaluator 9 用例 + transition 6 用例 = 15 总数（MD-012 声明 8 + DD-M 补足边界 5 + 异常 2）
- **决策理由**: MD-012 测试策略声明 "8 用例"，本框架补足到 15 以提升边界与异常覆盖率
- **拒绝的替代方案**:
  - 方案A: 严格 8 用例 — 拒绝理由: 边界与异常覆盖不足
  - 方案B: 20+ 用例 — 拒绝理由: 过度测试，维护成本高
- **影响范围**: tests/unit/test_stage/ 全部
- **相关FDR**: 无
- **来源标注**: [DD-001:MD-012 测试策略] + [DD-M推断:依据=测试覆盖目标≥80%]

## FDR-M012-006 Performance 字段含 current_stage

- **决策编号**: FDR-M012-006
- **决策标题**: Performance 数据类包含 current_stage 字段
- **决策状态**: 已接受（标注 DD-M 推断）
- **决策内容**: Performance dataclass 显式包含 current_stage 字段
- **决策理由**: evaluator 在 hysteresis 判定中需对比 proposed_stage 与 current_stage；MD-012 evaluate(performance) 签名未明确包含 current_stage，需在数据载体中显式表达
- **拒绝的替代方案**:
  - 方案A: current_stage 作为 evaluator 内部属性 — 拒绝理由: evaluator 无状态，违反设计
  - 方案B: 独立 StageContext 类 — 拒绝理由: 过度设计，破坏 Performance 内聚性
- **影响范围**: Performance 数据类 / StageEvaluator.evaluate()
- **相关FDR**: 无
- **来源标注**: [DD-M推断:依据=MD-012 evaluate(performance) 签名 + hysteresis 判定需求]

---

## 来源标注汇总

[DD-001:FS-012/MD-012] + [DD-M推断:依据=Strategy 模式 + 教学领域常识 + 单一职责原则]
