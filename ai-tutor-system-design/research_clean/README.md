# research_clean — 第一次清洗后的资料

> 阶段 2 产物：对 `research_raw/` 同名文件去噪后的版本。  
> 用途：抽取知识树（`research_knowledge/`）的直接输入。

## 清洗方法

| 项 | 处理 |
|---|------|
| HTML 残留（`<div>` / `<span>` / cookie 提示） | 删除 |
| 站点导航 / 页脚 / 评论区 | 删除 |
| 广告 / 推荐阅读 / "Related Posts" | 删除 |
| 代码块 / 引用块 | 保留 |
| 段内换行 | 合并 |
| 图片引用 `![](url)` | 保留并保留 URL |
| 文献引用 `[N]` / `(Author, Year)` | 保留 |

## 文件一一对应

`research_clean/X.md` 是 `research_raw/X.md` 清洗后的版本，文件名一致以便对照。

## 注意

- 如果原始内容变动，要重跑 raw → clean → knowledge 整条链路，不要只改 clean。
- 清洗工具：`crawl4ai` 的 `MarkdownGenerator` + 手工补正。
