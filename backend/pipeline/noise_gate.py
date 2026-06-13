"""backend.pipeline.noise_gate —— KG 噪声红线（M-014 验收红线：噪声<5%）。

把 v1 `is_noise_title`（FIX-A/B/K/M 累积的禁类分类器：裸文件名/代码注释/整句话/
骨架节名/时间戳/截断标题…）包成可查询的门禁：给一组概念名，算禁类占比并对阈值判定。

走向决议 §五-4：该红线显式挂 M-014——内容级抽取后噪声率必须 <5%，换体裁出新形态即回灌
`is_noise_title`（v1 单一可信源）。
"""
from __future__ import annotations

from typing import Any

from servers.knowledge_mcp.kg_enrich_adapter import is_noise_title
from shared.errors import TutorError
from shared.models import ConceptRow, KnowledgeGraphRow

DEFAULT_THRESHOLD = 0.05


class NoiseGate:
    """概念名噪声审计 + <阈值 判定。"""

    def __init__(self, *, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold

    def audit(self, names: list[str]) -> dict[str, Any]:
        total = len(names)
        offenders = [n for n in names if is_noise_title(n)]
        rate = len(offenders) / total if total else 0.0
        return {
            "total": total,
            "noise_count": len(offenders),
            "noise_rate": round(rate, 4),
            "threshold": self.threshold,
            "passed": rate <= self.threshold,
            "offenders": offenders[:50],  # 上限防爆，全量在日志/db
        }

    def audit_kg(self, store: Any, kg_id: str) -> dict[str, Any]:
        """审计已建 KG（只读，不改任何数据）。"""
        with store.session() as s:
            if s.get(KnowledgeGraphRow, kg_id) is None:
                raise TutorError("KG_NOT_FOUND", hint=kg_id)
            names = [
                row.name_primary
                for row in s.query(ConceptRow).filter(ConceptRow.kg_id == kg_id).all()
            ]
        return {"kg_id": kg_id, **self.audit(names)}
