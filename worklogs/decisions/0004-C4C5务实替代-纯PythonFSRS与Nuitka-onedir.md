# ADR-0004: C4/C5 务实替代——纯 Python FSRS-5 + Nuitka onedir（替 py-fsrs / PyInstaller onefile）

> 日期: 2026-06-15
> 状态: 已采纳

## 背景

C4/C5 两波各撞到一个"设计指定重依赖、本机装不上/不该用"的点：
1. **M-011 FSRS**：设计包 FDR-M011 要 `py-fsrs`。未安装，死系统代理（见持久记忆
   `dead-system-proxy-workaround`）下 pip 拉不下来；CI 不可复现。
2. **M-015 打包**：v2 打包文档原用 **PyInstaller onefile**，被 v3.1 走向决议 **R-01 证伪**
   （onefile 每次启动把科学计算栈解压到临时目录 → 冷启 8-15s + 杀软高误报）。

两处都遵循 C2/C3 已确立的务实哲学（ADR-0003 同源）：**重依赖能纯标准库替代就替代，且把
注入/升级点留好**。

## 决策

1. **FSRS-5 纯 Python 自实现**（`backend/strategy/fsrs.py`）：FSRS-5 算法（19 权重 + 标准
   stability/difficulty 更新公式 + retrievability 幂律）完全公开、纯数学，直接实现。无外部依赖、
   确定性、可测（含遗忘衰减/lapse 单调性断言）。`get_default_scheduler()` 单例满足 FDR-M011-001
   参数不漂移诉求。相对 v1 单参指数衰减是现代升级。
2. **Nuitka onedir（--standalone，硬禁 --onefile）**（`backend/build/`）：M-015 BuildOrchestrator
   生成的 Nuitka 命令**必须 --standalone**，测试设硬红线断言 `--onefile not in args`。真编译耗时
   但启动快、误报低、目录形态便于 electron extraResources 整目录引用。命令执行器可注入（CI/测试
   不真编译）。打包设计文档同步改写。

## 考虑的替代方案

| 点 | 采纳 | 拒绝 |
|----|------|------|
| FSRS | 纯 Python 自实现 FSRS-5 | 装 py-fsrs（死代理装不上/CI 不可复现）；退回 v1 指数衰减（丢 FSRS 升级） |
| 打包 | Nuitka onedir | PyInstaller onefile（R-01 证伪）；Nuitka onefile（同样自解压，失 onedir 优势） |

## 后果

- 正面：C4/C5 不被环境阻塞即可跑通 + 全测试覆盖；FSRS 行为与算法一致可验；打包命令正确性
  由测试守护（onedir 硬红线）。
- 负面：FSRS 权重为官方默认（未按本用户数据拟合，留作后续）；真 Nuitka 编译产物未在本环境
  实跑（需 C 编译器 + 5-15min，留待发布时真验，与 D1 Electron 真验同类环境受限项）。

## 相关

- 关联：ADR-0003（RAG 同源务实替代）/ 走向决议 R-01 / 持久记忆 dead-system-proxy-workaround
- 实现：`backend/strategy/fsrs.py`（commit e1aa27d）/ `backend/build/`（commit 1c2af16）
