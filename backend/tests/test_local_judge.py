"""LocalJudgeProvider（基础模式判分器）单测：可授 correct、克制 fluff、只判分。"""
from __future__ import annotations

import json

import pytest

from backend.teaching.local_judge import LocalJudgeProvider


def _judge(answer, definition="沿负梯度方向迭代最小化损失函数的优化方法", question=""):
    p = LocalJudgeProvider()
    prompt = (
        f'判断学生答案是否抓住了概念定义的核心。只输出 JSON：\n'
        f'概念: 梯度下降\n官方定义: {definition}\n'
        f'{"题目: " + question if question else ""}\n'
        f'学生答案: {answer}\n输出含 "correctness"'
    )
    resp = p.chat(messages=[{"role": "user", "content": prompt}])
    return json.loads(resp.content)


def test_substantive_answer_correct():
    out = _judge("沿着负梯度方向一步步迭代，最小化损失函数")
    assert out["correctness"] == "correct"


def test_empty_answer_incorrect():
    out = _judge("")
    assert out["correctness"] == "incorrect"


def test_offtopic_answer_not_correct():
    out = _judge("今天天气不错我想出去玩")
    assert out["correctness"] in ("partial", "incorrect")
    assert out["correctness"] != "correct"


def test_short_fluff_capped():
    out = _judge("梯度")  # 含名但极短 → 不给 correct
    assert out["correctness"] != "correct"


def test_non_scoring_prompt_raises():
    from shared.errors import TutorError

    p = LocalJudgeProvider()
    with pytest.raises(TutorError):
        p.chat(messages=[{"role": "user", "content": "给我讲个故事"}])


def test_supports_generation_false():
    assert LocalJudgeProvider.supports_generation is False
