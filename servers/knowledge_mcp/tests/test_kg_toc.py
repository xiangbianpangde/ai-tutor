"""knowledge-mcp 端到端：acquire + build_kg(depth=toc) 在 fixture markdown 上跑通。"""
from __future__ import annotations

from pathlib import Path

import pytest

from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
from servers.knowledge_mcp.kg_enrich_adapter import build_kg_toc
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow, User
from shared.storage import FileStore, RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


@pytest.fixture
def setup_user(tmp_db: RelationalStore) -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="yhn", display_name="Test"))
        s.commit()
    return tmp_db


def test_acquire_md_file(setup_user: RelationalStore, tmp_filestore: FileStore) -> None:
    assert FIXTURE.exists(), f"fixture missing: {FIXTURE}"
    manifest, corpus_id = acquire(
        subject="高等数学测试",
        version="v8",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=setup_user,
    )
    # corpus_id 由 subject 转拼音 + sha1 前 10 位组成
    assert manifest.total_chapters == 2  # "# 极限与连续" / "# 导数与微分"
    assert manifest.total_sections == 5  # 5 个 "## "


def test_build_kg_toc_full_flow(setup_user: RelationalStore, tmp_filestore: FileStore) -> None:
    manifest, corpus_id = acquire(
        subject="高等数学测试",
        version="v8",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=setup_user,
    )

    md_path = Path(manifest.file_paths["markdown"])
    kg_id, concepts, edges, quality, mermaid = build_kg_toc(
        corpus_id=corpus_id,
        subject_slug="gaoshu-test",
        markdown_path=md_path,
        db=setup_user,
    )

    # 节点数 = 2 章 + 5 节 + 10 小节 = 17
    assert len(concepts) == 17
    # 父子边 part_of: 17 - 2 个顶层 = 15
    part_of = [e for e in edges if e.type == "part_of"]
    assert len(part_of) == 15
    # 兄弟边 prerequisite_strong: 同级中除每组第一个之外都有；具体数与结构相关，>0 即可
    prereq = [e for e in edges if e.type == "prerequisite_strong"]
    assert len(prereq) > 0

    assert quality.overall in ("pass", "pass_with_warnings")
    assert "graph TD" in mermaid

    # 持久化校验
    with setup_user.session() as s:
        row = s.get(KnowledgeGraphRow, kg_id)
        assert row is not None
        assert row.node_count == len(concepts)
        assert row.edge_count == len(edges)

        concept_count = s.query(ConceptRow).filter_by(kg_id=kg_id).count()
        assert concept_count == len(concepts)

        relation_count = s.query(RelationRow).filter_by(kg_id=kg_id).count()
        assert relation_count == len(edges)


def test_kg_concept_ids_match_regex(setup_user: RelationalStore, tmp_filestore: FileStore) -> None:
    """生成的所有 Concept.id 必须符合 spec 的 regex。"""
    import re

    from shared.schemas import CONCEPT_ID_PATTERN

    manifest, corpus_id = acquire(
        subject="高数",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=setup_user,
    )
    md_path = Path(manifest.file_paths["markdown"])
    _, concepts, _, _, _ = build_kg_toc(
        corpus_id=corpus_id,
        subject_slug="gaoshu",
        markdown_path=md_path,
        db=setup_user,
    )
    pattern = re.compile(CONCEPT_ID_PATTERN)
    bad = [c.id for c in concepts if not pattern.match(c.id)]
    assert not bad, f"non-conformant ids: {bad}"


# ----------------------------- FIX-A：标题治理（#22 回归） ----------------------------- #


def test_build_toc_skips_code_fences_and_noise_titles(tmp_path: Path) -> None:
    """代码块注释 / 来源文件名 / 分隔线 / URL / 整句 不再成为概念；问句式标题保留。"""
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc

    md = tmp_path / "noisy.md"
    md.write_text(
        "# 真实章节\n"
        "## 真实小节\n"
        "```python\n"
        "# ============================================================\n"
        "# 代码注释不是标题\n"
        "print('x')\n"
        "```\n"
        "## 01-edu.aliyun.com-087e03\n"
        "## ============\n"
        "## https://example.com/page\n"
        "## 新加坡和北京地域的API Key不同，要分开获取再分别配置环境变量；\n"
        "## 什么是大模型？\n"
        "## 另一个真实小节\n",
        encoding="utf-8",
    )
    concepts, _edges = _build_toc(subject_slug="t", markdown_path=md)
    names = [c.names[0] for c in concepts]
    assert names == ["真实章节", "真实小节", "什么是大模型？", "另一个真实小节"]


def test_quality_warns_on_duplicate_names(tmp_path: Path) -> None:
    """重复概念名只告警不静默去重（跨章同名小节合法，归并交给 merge_concepts）。"""
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc, _compute_quality

    md = tmp_path / "dup.md"
    md.write_text(
        "# 第一章\n## QwenTTS 服务配置\n# 第二章\n## QwenTTS 服务配置\n",
        encoding="utf-8",
    )
    concepts, edges = _build_toc(subject_slug="t", markdown_path=md)
    assert len(concepts) == 4  # 不去重
    q = _compute_quality(concepts, edges)
    assert any("重复概念名" in w for w in q.warnings)


def test_demote_headings_fence_aware() -> None:
    from servers.knowledge_mcp.kg_enrich_adapter import demote_headings

    text = "# 标题\n```\n# 代码注释\n```\n## 子标题"
    out = demote_headings(text, min_level=2)
    lines = out.splitlines()
    assert lines[0] == "## 标题"
    assert lines[2] == "# 代码注释"  # 代码块内不动
    assert lines[4] == "### 子标题"


# ------------------- FIX-K：web 语料噪声形态（FastAPI 复跑回归） ------------------- #
# 博客正文里未围栏的代码注释顶格出现时，`# 注释` 在 markdown 语法上就是标题，
# 围栏跳过救不了。FastAPI 复跑实测 30 抽样噪声 ≈60%，按文本特征补过滤。


def test_build_toc_skips_web_corpus_noise_titles(tmp_path: Path) -> None:
    """时间戳/裸文件名/装饰注释/emoji·箭头/批注引导/含逗号整句/尾冒号 不再成为概念。"""
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc

    md = tmp_path / "web_noisy.md"
    md.write_text(
        "# FastAPI 后端开发\n"
        "## 依赖注入\n"
        "# 2025-04-24 14:25:07\n"
        "# main.py\n"
        "# deps.py（追加）\n"
        "# ===== 商品路由 =====\n"
        "# ✅ 保留时区信息\n"
        "# Code below omitted 👇\n"
        "# require_admin → get_current_user\n"
        "# 正确：用异步HTTP客户端\n"
        "# 创建一个线程池，比如最多4个线程\n"
        "# FastAPI 自动解析整条依赖链：\n"
        '# 固定 realm="protected"\n'
        '# DATABASE_URL = "postgresql://user:password@postgresserver/db"\n'
        "# (1)!\n"
        "# .env.production\n"
        "# app/routers/users.py\n"
        "# FastAPI_Study/FastAPI框架学习/03-请求与响应 at main\n"
        "# asyncio.run(demo_async_patterns())\n"
        "# 启动：uvicorn main:app --reload\n"
        "# 关于FastAPI生产环境部署是否仍需Gunicorn及两种启动方式差异的 ...\n"
        "# 可以！async def 和普通 def 都支持\n"
        "# Do some sequential stuff to create the burgers\n"
        "# this will record details of a successful validation to logfire\n"
        "## ① 编号小节保留\n"
        "## What is Dependency Injection\n"
        "## 第三层：服务层\n",
        encoding="utf-8",
    )
    concepts, _edges = _build_toc(subject_slug="t", markdown_path=md)
    names = [c.names[0] for c in concepts]
    assert names == [
        "FastAPI 后端开发",
        "依赖注入",
        "① 编号小节保留",
        "What is Dependency Injection",
        "第三层：服务层",
    ]


# ------------- FIX-M：论文/文档骨架节名（换体裁攻击 2026-06-13 回归） ------------- #
# 学术论文 PDF（mineru→翻译）语料的骨架节名在 FIX-K 12 类规则外：
# AAAI 论文实测 摘要/致谢/参考文献 = 3/19 概念（15.8%）超 5% 红线。
# 只杀无歧义纯骨架；引言/结论/相关工作 常含实质内容，保留为弱概念（宁留勿误杀）。


def test_build_toc_skips_paper_skeleton_titles(tmp_path: Path) -> None:
    """摘要/致谢/参考文献/目录/附录A/Abstract/References 不再成为概念；
    引言/结论/相关工作/含实名的附录章保留。"""
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc, is_noise_title

    md = tmp_path / "paper.md"
    md.write_text(
        "# MemoryART: 多记忆模型增强大语言模型\n"
        "## 摘要\n"
        "## 引言\n"
        "## 相关工作\n"
        "## 情景记忆\n"
        "## 实验\n"
        "## 结论\n"
        "## 致谢\n"
        "## 参考文献\n",
        encoding="utf-8",
    )
    concepts, _edges = _build_toc(subject_slug="t", markdown_path=md)
    names = [c.names[0] for c in concepts]
    assert names == [
        "MemoryART: 多记忆模型增强大语言模型",
        "引言",
        "相关工作",
        "情景记忆",
        "实验",
        "结论",
    ]

    # 英文骨架与扩展骨架形态
    for t in ("Abstract", "References", "Bibliography", "Acknowledgments",
              "目录", "附录 A", "Appendix B", "索引", "版权声明", "作者简介"):
        assert is_noise_title(t), f"骨架节名未被过滤: {t!r}"
    # 含实名的附录章 / 实质内容节 不误杀
    for t in ("附录A 矩阵代数基础", "Appendix A Matrix Algebra", "引言", "结论"):
        assert not is_noise_title(t), f"内容节被误杀: {t!r}"


def test_strip_site_suffix() -> None:
    """来源页标题剥站点尾巴（命中站点关键词才剥，普通标题不受影响）。"""
    from servers.knowledge_mcp.kg_enrich_adapter import strip_site_suffix

    assert strip_site_suffix("路径参数 - FastAPI - FastAPI 框架") == "路径参数"
    assert (
        strip_site_suffix("【框架篇二】FastAPI路由与请求处理 - 技术栈")
        == "【框架篇二】FastAPI路由与请求处理"
    )
    assert strip_site_suffix("FastAPI生产部署指南 - 一名程序媛呀 - 博客园") == "FastAPI生产部署指南"
    assert (
        strip_site_suffix("FastAPI依赖注入系统及调试技巧 - SegmentFault 思否")
        == "FastAPI依赖注入系统及调试技巧"
    )
    assert strip_site_suffix("12、Fastapi 请求与响应 - JoPa学习笔记") == "12、Fastapi 请求与响应"
    assert strip_site_suffix("依赖项 - FastAPI") == "依赖项"  # 官方文档尾巴
    assert (
        strip_site_suffix("详解FastAPI如何利用异步编程模型避免IO堵塞-开发者社区-阿里云")
        == "详解FastAPI如何利用异步编程模型避免IO堵塞"
    )  # 无空格连字符尾巴
    assert strip_site_suffix("依赖注入 - 高级用法") == "依赖注入 - 高级用法"  # 非站点尾巴不剥
    assert strip_site_suffix("FastAPI——快速入门") == "FastAPI——快速入门"  # 未剥离不重组分隔符
    assert strip_site_suffix("JWT密钥和算法") == "JWT密钥和算法"


def test_rebuild_same_corpus_replaces_kg(
    setup_user: RelationalStore, tmp_filestore: FileStore
) -> None:
    """同一语料重建：同 kg_id 整体替换，不再主键冲突（修过滤器后重跑是常规操作）。"""
    manifest, corpus_id = acquire(
        subject="重建测试",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=setup_user,
    )
    md_path = Path(manifest.file_paths["markdown"])
    kg_id_1, concepts_1, *_ = build_kg_toc(
        corpus_id=corpus_id, subject_slug="rebuild-t", markdown_path=md_path, db=setup_user
    )
    kg_id_2, concepts_2, *_ = build_kg_toc(
        corpus_id=corpus_id, subject_slug="rebuild-t", markdown_path=md_path, db=setup_user
    )
    assert kg_id_2 == kg_id_1
    with setup_user.session() as s:
        assert s.query(KnowledgeGraphRow).filter_by(kg_id=kg_id_1).count() == 1
        assert s.query(ConceptRow).filter_by(kg_id=kg_id_1).count() == len(concepts_2)
        assert s.query(RelationRow).filter_by(kg_id=kg_id_1).count() > 0


def test_rebuild_subject_with_new_corpus_replaces_old_root_kg(
    setup_user: RelationalStore, tmp_path: Path
) -> None:
    """concept.id 不含 corpus 命名空间、corpus_id 含时间戳：同科目重新采集后重建
    曾必然撞旧 KG 概念主键（ACP 只能手工删库绕过）→ 撞 id 的旧根版本 KG 整体替换。"""
    from servers.knowledge_mcp.kg_enrich_adapter import build_kg_toc

    md = tmp_path / "m.md"
    md.write_text("# 章节甲\n## 小节乙\n", encoding="utf-8")
    kg_id_1, *_ = build_kg_toc(
        corpus_id="same-subject-aaa111", subject_slug="resub", markdown_path=md, db=setup_user
    )
    md.write_text("# 章节甲\n## 小节乙\n## 小节丙\n", encoding="utf-8")
    kg_id_2, concepts_2, *_ = build_kg_toc(
        corpus_id="same-subject-bbb222", subject_slug="resub", markdown_path=md, db=setup_user
    )
    assert kg_id_2 != kg_id_1
    with setup_user.session() as s:
        assert s.get(KnowledgeGraphRow, kg_id_1) is None  # 旧根版本被替换
        assert s.query(ConceptRow).filter_by(kg_id=kg_id_1).count() == 0
        assert s.query(ConceptRow).filter_by(kg_id=kg_id_2).count() == len(concepts_2)


def test_toc_concept_carries_body_not_source_leak(tmp_db, tmp_filestore) -> None:
    """独立验收发现：toc 概念应带标题下正文(真讲解)，不外露"来自 xxx 行 N 的章节标题"。"""
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from shared.models import User

    with tmp_db.session() as s:
        s.add(User(id="yhn", display_name="T"))
        s.commit()
    md = tmp_filestore.path("biolab.md")
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("# 光合作用\n绿色植物利用光能合成有机物并释放氧气的过程。", encoding="utf-8")
    manifest, corpus_id = acquire(
        subject="生物", version="v1",
        sources=[AcquireSource(type="file", uri=str(md))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    _kg, concepts, *_ = build_kg_toc(
        corpus_id=corpus_id, subject_slug="bio",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    c = concepts[0]
    assert "光能" in c.definition  # 带真正文
    assert c.definition != c.names[0]  # 不再只是标题
    assert "章节标题" not in c.informal_description  # 不外露源行号脚注
