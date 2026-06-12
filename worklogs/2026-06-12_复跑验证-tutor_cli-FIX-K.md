# 2026-06-12 · 新科目复跑验证 + tutor_cli + FIX-K

## 背景

STATUS「下一步」第 1 项：用**新科目**端到端复跑验证 FIX-A~J（acquire(web,deepen) →
build_kg(full) → review_kg → digest(study_pack) → 教学 15-20 步），并按「接手挑战清单」
逐项过堂。新科目选 **FastAPI 后端开发**（v2 技术栈，web 语料丰富）。

## 做了什么

### 1. tutor_cli —— 挑战「裸手跑通」的结构性前提（v1 缓解 #8/#21）

复跑第一步就撞上结构性缺口：仓库里**没有任何参数化端到端入口**——
`scripts/step*.py`、`acp_*.py` 全是把 subject/corpus_id/session_id 硬编码进源码的
一次性脚本（#8「需人引导」的实体证据，ACP 重建 KG 甚至要靠脚本手工删库）。

新增 `scripts/tutor_cli.py`（一个文件，11 个子命令）：

```
acquire --subject S --web 主题 --file 路径 [--deepen] [--translate]
build [--corpus ID] [--depth full]     # 自动建 User/Subject 行（曾是手写胶水）
review [--kg ID] [--sample 30]         # quality gate + 低置信 + 随机抽样过堂
digest [--kg ID] [--formats study_pack]
learn / next / advance / answer / ask / progress / status
```

省略 ID 参数时自动沿用上一步结果（`data/cli_state.json`，已 gitignore）。
任何新科目从采集到教学全程零脚本、零 SQL。被替代的 17 个一次性脚本随本迭代
归档后删除（见 git 历史）。

### 2. 复跑发现的新问题与修复（FIX-K，全部带回归测试）

**第一轮 build(full)：369 概念，随机抽 30 噪声率 ≈60%** —— FIX-A 的围栏跳过对
ACP 类语料有效，但 web 博客语料的噪声形态完全不同：HTML→MD 转换后**未围栏的
代码以列 0 顶格出现**，`# 注释` 在 markdown 语法上就是合法标题。逐类修复：

| 修复 | 内容 | 实测命中 |
|------|------|---------|
| K1 噪声标题过滤扩展（12 类） | 时间戳 / 裸代码文件名与相对路径(main.py、app/routers/users.py) / dotfile(.env.production) / 装饰注释(`===== x =====`) / emoji·箭头 / 批注引导(`正确：``详细介绍：`) / 含逗号整句 / 尾冒号 / 中段感叹句 / 代码行(`realm="x"`、`asyncio.run(x())`、`--reload` 命令、任意 URL scheme) / 纯数字标注(`(1)!`) / 截断搜索标题(`…的 ...`) / GitHub 路径(`at main`) / 英文整句注释(功能词≥2) | `2025-04-24 14:25:07`、`users.py`、`✅ 保留时区信息`、`创建一个线程池，比如最多4个线程`、`DATABASE_URL = "postgresql://..."`、`Do some sequential stuff to create the burgers`、`启动：uvicorn main:app --reload` |
| K2 站点尾巴剥离 | `strip_site_suffix` 两遍：带空格分隔段命中站点关键词才剥（可再剥一段短作者尾）；无空格连字符段仅剥关键词命中段；未剥离原样返回不重组分隔符 | `路径参数 - FastAPI - FastAPI 框架`→`路径参数`、`…避免IO堵塞-开发者社区-阿里云`→`…避免IO堵塞` |
| K3 同科目重建撞主键 | `concept.id` 不含 corpus 命名空间 + `corpus_id` 含时间戳 → **同科目重新采集后重建必然 IntegrityError**（ACP 当时靠 acp_merge_and_rebuild.py 手工删库绕过）。`_persist_kg` 现在：同 kg_id 整体替换；撞概念 id 的同科目旧根版本 KG 整体替换并告警；versioned 派生 KG（`@short` 后缀 id）不受影响 | 本次第二轮重建即触发 `kg.rebuild.replace_subject_kg` |
| K4 deepen 子面重复采集 | `_merge_markdown` 按 (来源URL, 正文sha1) 去重——多个子面搜回同一篇文章只入料一次 | 重名概念组 49→30（第二轮） |
| K5 study_pack 切不动 | web 语料结构 `H1=科目→H2=主题→H3=来源`，只切到 H2 → 1.4MB 切成 3 个 ⚠️超长大块。`_split_chapter` 改为递归下钻 H3-H6 | 见下产物清单 |

### 3. 复跑结果（FastAPI 后端开发）

- acquire(web×3, deepen=true)：每主题 20-27 来源 → `00_corpus.md` 99,174 行 / 1.39MB
  （wikipedia 引擎被墙失败，DDG/google.hk/tavily 兜底正常；`research.merge.skip_dup` 生效）
- build(full)：六轮过滤迭代 **369 → 242 → 215 → 204 → 203 → 199** 概念（每轮抽 30 人工
  归类→补规则→重建，`kg.rebuild.replace` 幂等替换全程无手工删库）；最终 quality：
  coverage 1.00 / isolated 0 / cycles 0 / avg_conf 0.90 / 缺示例 0 / 重名 24 组
- 噪声过堂：抽样有方差（第 5 轮抽中此前漏网的路径类），最终改**全量扫描** 199 个概念名
  —— 禁类命中 **1/199（0.5%）**，且为边缘形态「main.py 添加」（含文件名的步骤标题）；
  裸文件名/路径/代码行/整句/时间戳 = **0**（web 语料起点 ≈60%，ACP 修复前基线 35%）
- digest(study_pack)：**75 份分片 + 索引**（总 2216 分钟，每份目标 15-30 分钟；18 份因
  来源文章内部无更深标题仍标 ⚠️超长）——修复前同语料只能切 3 个 ~1100 分钟大块
- 教学 21 步（sess-c882f9cba045）：掌握 2/199 概念（1 与 1.1 → 0.94+），动作分布
  show_example 8 / ask_question 6 / explain 3 / give_exercise 3 / break_suggestion 1；
  增益回路在三次攻击造成的波谷后**自发**给出 break_suggestion

### 4. 挑战清单过堂结果

- [x] **裸手跑通**：全程 tutor_cli，0 临时脚本（CLI 本体是正式带测试的常驻工具）✅
- [x] **噪声率过堂**：全量 0.5%（1 例边缘）<5%，三禁类 = 0 ✅
- [x] **答非所问攻击**：3 题沾边不答题（夸框架 / 背 HTTP 方法 / 谈密码安全）→
  **3/3 判 incorrect**，诊断准确（reading_error / overgeneralization）——FIX-D 前同类
  套话曾判 correct +0.298 ✅
- [x] **死循环回归**：21 步 give_exercise 占比 **15%** << 50% 红线，讲解类 55% 充分穿插
  （历史失败模式：15 步 14 步连发练习）✅
- [x] **休息触发**：`test_engine_t3.py` 两条 FIX-F 测试通过——6 轮**全对**回答 +
  freezegun 走表 50 分钟 → `study_streak` 休息建议触发；间隔 >15 分钟正确重置不触发。
  非答错驱动 ✅

## 验证

- knowledge_mcp 190 / digest_mcp 49 全过（新增 FIX-K 回归 9 条）
- 全量回归：**792 passed**（基线 786）

## 遗留（回灌 v2）

- 类别失衡（98% method）与重名概念组残留（跨主题重复语料）→ v2 M-014 内容级抽取/整理
- CSDN 侧边栏离题推荐文章混入语料（清洗层漏网）→ research-tool clean 阶段或 M-014
- 概念名仍以"来源文章标题/小节标题"为主——标题驱动抽取的天花板，非 v1 可修
- `(1)!` 类 mkdocs 标注、`· 作者名` 等长尾形态靠枚举过滤不可持续，v2 应换内容级判别
