"""把任意标题（中文/英文/混排）转成符合 Concept.id 规范的 ASCII slug。

策略:
1. 中文 → 拼音（不带声调）
2. 非字母数字 → -
3. 全转小写
4. 空 → "untitled"
"""
from __future__ import annotations

import re

from pypinyin import Style, lazy_pinyin


_NON_SAFE = re.compile(r"[^a-z0-9_]+")


def slugify(text: str, *, separator: str = "_") -> str:
    """转 [a-z0-9_] slug。如果转出来是空，返回 'untitled'。"""
    if not text:
        return "untitled"
    parts = lazy_pinyin(text, style=Style.NORMAL)
    s = "".join(parts).lower()
    s = _NON_SAFE.sub(separator, s).strip(separator)
    return s or "untitled"


def slugify_dash(text: str) -> str:
    """concept.id 的 subject 段允许 `-`。"""
    return slugify(text, separator="-")
