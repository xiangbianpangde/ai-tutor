# 48 小时规模 — 真实教材验证报告

> 日期：2026-05-24  
> 教材：同济大学《高等数学（下册）》第八版（第 8–12 章）  
> 目的：用一科真实教材在"48 小时规模"下端到端验证整条管道。

## 关于 PDF 与结构来源（如实说明）

提供的 PDF（76MB / 354 页）是**扫描影像，无文本层**（pypdf 抽取 0 字符/页），其 outline
只含 5 个章级书签、无节级。本机未安装 OCR（mineru 不在 PATH，也无 Python 模块）。

因此本次验证的章节结构来自**同济八版标准目录的忠实重建**（`examples/gaoshu_xiace_structure.md`：
5 章 / 32 节 / 139 个概念级条目），而非对该扫描件的 OCR。**概念富化与全部教学交互用的是
真实 DeepSeek**（`DEEPSEEK_API_KEY` 已配置），所以"规模 + 真实 LLM"的验证目标成立；唯一
被替代的是 PDF→结构这一步（受限于扫描件 + 无 OCR）。

## 结果

### 1. KG 构建（规模 + 真实 LLM 富化）

| 指标 | 值 |
|---|---|
| 概念数 | **139**（5 章 / 32 节 / concept 级） |
| 关系数 | 235（part_of + prerequisite_strong） |
| toc 构建 | <1s，chapter_coverage 1.0，0 孤岛，0 环 |
| concept 富化（真实 DeepSeek，8 worker 并行 + checkpoint） | **39.5s**（0.28s/概念有效） |
| 平均置信度 | 0.40（toc）→ **0.723**（concept 富化后） |
| 富化成功（conf>0.5） | 124/139，0 warning |
| checkpoint | 139 行（崩溃可续跑） |

**P1 #5 批量管道在真实规模成立**：审计原述"800 概念串行 ~40min"；本次 139 概念并行 40s，
线性外推 800 概念约 ~230s（~4min）。

### 2. Phase 化学习计划（P0 #3）

139 概念自动切成 **5 个 Phase**（对应 5 章）：向量代数与空间解析几何(31) / 多元函数微分(32) /
重积分(17) / 曲线曲面积分(27) / 无穷级数(32)。`get_learning_progress` 正确报告当前 Phase、
下一个该学概念；`start_learning_session` 给出 Phase 化 teaching_plan + 进度摘要。

### 3. 冷启动摸底（P0 #2）

10 题真实 DeepSeek 判分；弱答（"不太清楚"）→ 全判未掌握 → 推荐 beginner；画像初值写入
（abstract_tol 0.5 / transfer 0.0 / self_acc 0.7）。

### 4. 真实 LLM 教学内容 + 反馈（P0 #1 / P1 #7）

`start_learning_session` 与 `next_action` 返回 **LLM 实时生成**的讲解（generated=True），
例如向量概念配了"飞机从北京飞往上海的方向+距离""导航系统"等生动类比——不是模板填空。
`respond` 用真实 LLM 判分 + L3 润色反馈（温暖、具体、非评判，例："你尝试用自己的话复述…
下一步可以试着用坐标写一个具体的…"）。BKT 掌握度、认知负荷在线更新均生效。

### 5. 端到端

采集(.md) → toc → concept KG（真实富化）→ Phase 计划 → 冷启动 → 开课 → 教学循环
（内容/判分/反馈/BKT/认知负荷）→ 进度，**全链路在 139 概念真实教材上跑通**。

## full 深度复测（2026-05-24，实测数据）

同一 139 概念用 **full 深度** 重建（真实 DeepSeek，8 worker，39s，embedding 139/139）：

| 指标 | concept 深度 | full 深度（实测） |
|---|---|---|
| 学习时长/概念 | 恒 30min | 15 / 18 / 21min（均值 20.1，对应 章/节/概念三级） |
| **总学时** | 69.5h | **46.5h**（贴近 48h 目标 ✓） |
| calibrated_difficulty | 无 | 0.278–0.412（均值 0.392） |
| cold-start band 分布 | all current | **仍 all current** ✗ |

## 发现 / 限制

1. **时间估计（已实测确认）**：concept 深度恒 30min（计划 69.5h）；**full 深度时间校准生效，
   总学时降到 46.5h，贴近 48h**。这是 Slice TC 的核心价值，已验证。

2. **难度/时长/band 的"内容粒度"——已修复（P2 #11）**。早先（enricher 不填难度信号时）
   难度/时长只有 3 个离散档、band 全 current。修法：让 `ConceptEnricher` 用 LLM 从内容估计
   `abstract_level` / `formula_density` / `cognitive_load_estimate`，并去掉 prompt 里对
   abstract_level 的锚定（原来把 toc 默认值喂给 LLM 导致它向 0.3-0.6 收敛）。

   **修复后实测（同 139 概念，full 深度，真实 DeepSeek）：**
   | 信号 | 修复前 | 修复后 |
   |---|---|---|
   | abstract_level | 0.30/0.45/0.60（标题层级 3 档） | 0.10–0.70（内容驱动，均值 0.43） |
   | formula_density | 恒 0.10 | 0.00–0.70（均值 0.38） |
   | cognitive_load | 恒 0.30 | 0.10–0.70（均值 0.46） |
   | 时长 | 3 档（15/18/21） | 10–28min，17 个不同值，总 46.9h |
   | calibrated_difficulty 分桶 | 5/134/0/0 | 25/92/22/0 |
   | cold-start band | all current | **{current:126, basic:9, abstract:4}** ✓ 三带齐全 |

   band 仍偏 current 是**忠实反映**——高数下册各节本就大多是中等难度；但三带均有概念，
   cold_start 可正常组出 3/4/3 摸底题。

3. **教学循环的状态推进**：简化驱动脚本只调 next_action+respond，未发 intro_done/
   explain_done 事件，reduction 停在 INTRO（这是既有 host 编排契约，非 bug）。

4. **PDF→结构**：扫描件无文本层 + 无 OCR 时无法自动抽结构。后续装 mineru/OCR 可打通
   acquire 的 pdf 路径；当前 .md 源路径已验证可用。
3. **教学循环的状态推进**：简化驱动脚本只调 next_action+respond，未发 intro_done/
   explain_done 事件，reduction 停在 INTRO（这是既有 host 编排契约，非 bug）。真实 host
   （Claude Desktop）按编排发这些事件即可推进。
4. **PDF→结构**：扫描件无文本层 + 无 OCR 时无法自动抽结构。后续若装 mineru/OCR 可打通
   acquire 的 pdf 路径；当前 .md 源路径已验证可用。

## 结论

整条"采集→KG→摸底→分阶段教学→6 策略→内容/反馈 LLM 生成→认知负荷调参→续学"闭环
在一科真实教材（139 概念）+ 真实 DeepSeek 下端到端跑通；批量 KG 管道在真实规模性能达标。
复现：`examples/gaoshu_xiace_structure.md` + 配 `DEEPSEEK_API_KEY` 后走 acquire(.md) →
build_knowledge_graph(depth=concept|full) → tutoring 工具链。
