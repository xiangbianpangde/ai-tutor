# 文件框架结构 — M-012 阶段校准（Strategy）

> 模块编号: M-012
> 模块名称: 阶段校准（Stage Calibration）
> 设计模式: Strategy
> 来源标注: [DD-001:FS-012/MD-012] + [DD-M推断:依据=Python src layout + Strategy 模式]

---

## M-012 文件框架

```
src/aitutor/stage/
├── __init__.py            ← [职责: 模块入口，导出公共 API（StageEvaluator/StageTransition/evaluate_stage/transition_stage/STAGE_MIN/STAGE_MAX/Performance/DailySample）]
├── evaluator.py           ← [职责: 阶段评估器，滑动窗口 + hysteresis 防抖，决定目标档位]
│   - [类1: StageEvaluator 注释（评估主类）]
│   - [类2: Performance 注释（表现数据载体）]
│   - [类3: DailySample 注释（每日样本）]
│   - [函数1: evaluate_stage 注释（顶层入口）]
└── transition.py          ← [职责: 档位转换器，can_up/can_down/clamp + 顶层 transition_stage]
    - [类1: StageTransition 注释（转换主类）]
    - [函数1: transition_stage 注释（顶层入口）]

tests/unit/test_stage/
├── __init__.py
├── test_evaluator.py      ← [职责: StageEvaluator + evaluate_stage 测试（9 用例：核心4+边界3+异常2）]
│   - [测试场景1: 高表现升档] [断言: new_stage > current] [Mock: 无]
│   - [测试场景2: 低表现降档] [断言: new_stage < current] [Mock: 无]
│   - [测试场景3: 顶层函数一致性] [断言: 结果相等] [Mock: 无]
│   - [测试场景4: 综合得分聚合] [断言: score in [0,1]] [Mock: 无]
│   - [测试场景5: 数据不足保持] [断言: 返回 current] [Mock: 无]
│   - [测试场景6: 滞回防抖] [断言: tail 不满足保持] [Mock: 无]
│   - [测试场景7: accuracy 越界] [断言: ValueError] [Mock: 无]
│   - [测试场景8: 窗口非法] [断言: ValueError] [Mock: 无]
│   - [测试场景9: 滞回非法] [断言: ValueError] [Mock: 无]
└── test_transition.py     ← [职责: StageTransition + transition_stage 测试（6 用例：核心3+边界2+异常1）]
    - [测试场景1: 可升档] [断言: 中间可升/最高不可] [Mock: 无]
    - [测试场景2: 可降档] [断言: 中间可降/最低不可] [Mock: 无]
    - [测试场景3: 转换规则] [断言: 跨度1合法/跨度2拒绝/相同幂等] [Mock: 无]
    - [测试场景4: clamp 越界] [断言: 0→1, 7→5] [Mock: 无]
    - [测试场景5: 转换钳制] [断言: 越界按钳制计算] [Mock: 无]
    - [测试场景6: 构造异常] [断言: 默认构造不抛] [Mock: 无]
```

---

## 文件间依赖关系

```
tests/unit/test_stage/test_evaluator.py
    ↓
src/aitutor/stage/evaluator.py
    ↓ (clamp)
src/aitutor/stage/transition.py
    ↑
src/aitutor/stage/__init__.py (导出)

tests/unit/test_stage/test_transition.py
    ↓
src/aitutor/stage/transition.py
```

---

## 文件结构合规检查（5 项）

| 检查项 | 检查标准 | 通过 | 备注 |
|--------|---------|------|------|
| 目录层级 | ≥2 层 | ✅ | src/aitutor/stage/ + tests/unit/test_stage/ 均 ≥2 层 |
| 文件命名 | snake_case | ✅ | evaluator.py / transition.py / test_evaluator.py / test_transition.py |
| 文件职责 | 单一明确 | ✅ | evaluator 评估 / transition 转换 / tests 测试 |
| 依赖关系 | 无循环 | ✅ | evaluator → transition，单向依赖 |
| 最佳实践 | src layout + 包入口 | ✅ | __init__.py 导出公共 API；tests 与 src 平级 |

合规度: **高**（5/5 全通过）

---

## 来源标注

[DD-001:FS-012/MD-012] + [DD-M推断:依据=Python src layout + Strategy 模式拆分]
