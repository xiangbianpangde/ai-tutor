"""digest() 编排：按 formats 分派到各 generator。

支持的 format（全部已实现）:
- mindmap / notes / quiz
- simulation   自包含 HTML 交互闪卡
- multi_agent  三角色对话脚本 JSON（llm 给定时 LLM 生成，否则模板）
- slides       自包含 HTML 幻灯（装 python-pptx 则升级 .pptx）
- audio        朗读讲稿 .md（装 edge-tts 则合成 .mp3）
- study_pack   语料按章节拆成 15-30 分钟/份的小文件 + 索引（#2：告别一次读 5 万行）

设计:
- KG 必须存在（KG_NOT_FOUND 抛 TutorError）
- 单 format 失败不影响其他 format（warnings 累计）
- 总入口异常才上抛
"""
from __future__ import annotations

from pathlib import Path

from dataclasses import dataclass

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import KnowledgeGraphRow
from shared.schemas import ArtifactURI, DigestResult
from shared.storage import RelationalStore


@dataclass
class DigestRunResult:
    """orchestrator 返回值，带 warnings；spec 的 DigestResult 只有 artifacts。

    需要 spec 型对象时调用 .to_schema 属性。
    """

    artifacts: list[ArtifactURI]
    warnings: list[str]

    @property
    def to_schema(self) -> DigestResult:
        return DigestResult(artifacts=self.artifacts)

from .audio import generate_audio
from .mindmap import generate_mindmap
from .multi_agent import generate_multi_agent
from .notes import generate_notes
from .quiz import generate_quiz
from .simulation import generate_simulation
from .slides import generate_slides
from .study_pack import generate_study_pack

logger = get_logger("digest_mcp.orchestrator")


_DEFAULT_FORMATS = ["mindmap", "quiz"]
_ALL_FORMATS = {
    "mindmap", "notes", "quiz",
    "slides", "audio", "simulation", "multi_agent",
    "study_pack",
}


def digest(
    *,
    db: RelationalStore,
    kg_id: str,
    out_dir: Path,
    formats: list[str] | None = None,
    quiz_count: int = 10,
    quiz_seed: int | None = None,
    grade: str = "college",
    llm=None,
) -> "DigestRunResult":
    """对给定 KG 生成多种产物，返回 DigestRunResult（带 warnings）。

    用法对照 spec DigestResult 时，调 `.to_schema` 拿 spec 型对象。
    """
    formats = formats or _DEFAULT_FORMATS

    # 预检 KG 存在
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[ArtifactURI] = []
    warnings: list[str] = []

    for fmt in formats:
        try:
            if fmt == "mindmap":
                artifacts.append(generate_mindmap(db=db, kg_id=kg_id, out_dir=out_dir))
            elif fmt == "notes":
                artifacts.append(generate_notes(db=db, kg_id=kg_id, out_dir=out_dir, grade=grade))
            elif fmt == "quiz":
                artifacts.extend(
                    generate_quiz(
                        db=db, kg_id=kg_id, out_dir=out_dir,
                        count=quiz_count, seed=quiz_seed,
                    )
                )
            elif fmt == "simulation":
                artifacts.append(generate_simulation(db=db, kg_id=kg_id, out_dir=out_dir))
            elif fmt == "multi_agent":
                artifacts.append(
                    generate_multi_agent(db=db, kg_id=kg_id, out_dir=out_dir, llm=llm)
                )
            elif fmt == "slides":
                artifacts.append(generate_slides(db=db, kg_id=kg_id, out_dir=out_dir))
            elif fmt == "audio":
                artifacts.append(generate_audio(db=db, kg_id=kg_id, out_dir=out_dir))
            elif fmt == "study_pack":
                artifacts.extend(generate_study_pack(db=db, kg_id=kg_id, out_dir=out_dir))
            else:
                warnings.append(
                    f"未知 format={fmt!r}（支持: {', '.join(sorted(_ALL_FORMATS))}）"
                )
        except Exception as exc:  # noqa: BLE001 — 单 format 失败不应整体崩
            logger.warning("digest.format_failed", format=fmt, error=str(exc))
            warnings.append(f"format={fmt!r} 失败: {type(exc).__name__}: {exc}")

    logger.info(
        "digest.done",
        kg_id=kg_id,
        formats=formats,
        artifacts=len(artifacts),
        warnings=len(warnings),
    )
    return DigestRunResult(artifacts=artifacts, warnings=warnings)
