"""review_kg / update_kg / resolve_conflicts 三个 stub tool 的契约测试。

约束:
- 都能正常被 FastMCP 注册（mcp.list_tools 能看到）
- 调用时 raise DEPENDENCY_MISSING + hint 必须指向后续切片
"""
from __future__ import annotations

import pytest

from servers.knowledge_mcp import server as srv
from shared.errors import TutorError


def _unwrap(tool_obj):
    return getattr(tool_obj, "fn", None) or getattr(tool_obj, "func", None) or tool_obj


@pytest.mark.asyncio
async def test_review_kg_no_longer_stub_dispatches_to_impl() -> None:
    """K1.3: review_kg 已实现，不再 stub。无效 kg_id 应抛 KG_NOT_FOUND（不是 DEPENDENCY_MISSING）。"""
    fn = _unwrap(srv.review_kg)
    with pytest.raises(TutorError) as exc:
        await fn(kg_id="nonexistent", mode="quick")
    assert exc.value.code == "KG_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_kg_no_longer_stub_dispatches_to_impl() -> None:
    """K2.4: update_kg 已实现。无效 kg_id 应抛 KG_NOT_FOUND。"""
    fn = _unwrap(srv.update_kg)
    with pytest.raises(TutorError) as exc:
        await fn(kg_id="no-such", actions=[{"op": "approve_all"}])
    assert exc.value.code == "KG_NOT_FOUND"


@pytest.mark.asyncio
async def test_resolve_conflicts_no_longer_stub_dispatches_to_impl() -> None:
    """resolve_conflicts 已实现（5 种结构冲突检测）。无效 kg_id 应抛 KG_NOT_FOUND。"""
    fn = _unwrap(srv.resolve_conflicts)
    with pytest.raises(TutorError) as exc:
        await fn(kg_id="no-such-kg")
    assert exc.value.code == "KG_NOT_FOUND"


@pytest.mark.asyncio
async def test_all_three_stubs_registered_on_mcp() -> None:
    """FastMCP server 必须把三个 stub 注册成 tool，host LLM 才能发现存在性。"""
    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    assert "review_kg" in names
    assert "update_kg" in names
    assert "resolve_conflicts" in names
    # 同时确认 spine 已实现的 tool 也在
    assert "acquire_subject" in names
    assert "build_knowledge_graph" in names
