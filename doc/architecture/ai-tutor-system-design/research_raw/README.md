# research_raw — 调研原始爬取

> 阶段 1 产物：从公开 Web 抓回的未清洗 Markdown。  
> 用途：可追溯性 + 复算依据。下游 `research_clean/` 是去噪后的版本。

## 文件清单

| 文件 | 来源 | 抓取日期 | 抓取方式 |
|------|------|---------|---------|
| `openmaic_github.md` | https://github.com/openmaic/openmaic | 2026-05-18 | crawl4ai |
| `openmaic_website.md` | https://openmaic.org | 2026-05-18 | crawl4ai |
| `openmaic_medium.md` | https://medium.com 检索 OpenMAIC 命中页 | 2026-05-18 | crawl4ai |
| `openmaic_clawblog.md` | claw blog OpenMAIC 评测 | 2026-05-18 | crawl4ai |
| `notebooklm_google_blog.md` | https://blog.google NotebookLM 官方公告 | 2026-05-18 | crawl4ai |
| `notebooklm_wikipedia.md` | https://en.wikipedia.org/wiki/NotebookLM | 2026-05-18 | crawl4ai |
| `notebooklm_audio_blog.md` | NotebookLM 音频概览功能博客 | 2026-05-18 | crawl4ai |
| `notebooklm_support_audio.md` | Google support 音频概览文档 | 2026-05-18 | crawl4ai |
| `notebooklm_linkedin_arch.md` | LinkedIn 帖：NotebookLM 内部架构推测 | 2026-05-18 | crawl4ai |

## 注意

- 不要直接编辑这些文件。需要更新就重新抓取并替换。
- 抓取流程见根目录 `specs/dependency-list.md` "搜索 / 抓取" 段（DuckDuckGo + crawl4ai）。
- 二次清洗产出在 `research_clean/`，知识树主表在 `research_knowledge/00-主表.md`。
