"""slides generator — 自包含 HTML 演示幻灯片（可选升级 .pptx）。

默认：内联 HTML 分页幻灯（键盘 ←/→ 翻页，无 CDN，离线可用）。
若环境装了 python-pptx，则额外生成 .pptx 并返回它（PowerPoint 可编辑）。

幻灯结构：封面 → 每个 concept 一页（标题 + 定义 + 通俗解释 + 例子）。
"""
from __future__ import annotations

import html
import importlib.util
import json
from pathlib import Path

from shared.logging_config import get_logger
from shared.schemas import ArtifactURI
from shared.storage import RelationalStore

from ._kg_read import load_sorted_concepts

logger = get_logger("digest_mcp.slides")

_HAS_PPTX = importlib.util.find_spec("pptx") is not None


def _slides_data(kg, rows) -> list[dict]:
    slides: list[dict] = [{
        "title": f"{kg.subject_id}",
        "subtitle": f"共 {len(rows)} 个概念 · 自动生成演示",
        "body": [], "cover": True,
    }]
    for r in rows:
        full = r.full_json or {}
        body: list[str] = []
        if r.definition:
            body.append(f"定义：{r.definition}")
        if r.informal_description:
            body.append(f"通俗：{r.informal_description}")
        for e in (full.get("examples") or [])[:1]:
            if e.get("text"):
                body.append(f"例：{e['text']}")
        slides.append({"title": r.name_primary or r.id, "subtitle": "",
                        "body": body, "cover": False})
    return slides


_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{subject} — 幻灯片</title>
<style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ font-family: "Segoe UI","Microsoft YaHei",sans-serif; background:#000; color:#fff;
         height:100vh; overflow:hidden; }}
  .slide {{ display:none; height:100vh; padding:8vh 10vw; flex-direction:column;
           justify-content:center; }}
  .slide.active {{ display:flex; }}
  .slide.cover {{ align-items:center; text-align:center;
                 background:linear-gradient(135deg,#1e3a8a,#0f172a); }}
  h2 {{ font-size:40px; margin-bottom:24px; color:#93c5fd; }}
  .cover h2 {{ font-size:56px; color:#fff; }}
  .sub {{ font-size:22px; color:#94a3b8; margin-bottom:16px; }}
  li {{ font-size:24px; line-height:2; list-style:none; margin:8px 0;
       padding-left:20px; border-left:3px solid #3b82f6; }}
  #bar {{ position:fixed; bottom:0; left:0; height:4px; background:#3b82f6; transition:width .3s; }}
  #pg {{ position:fixed; bottom:16px; right:24px; color:#475569; font-size:14px; }}
</style></head><body>
<div id="deck"></div>
<div id="bar"></div><div id="pg"></div>
<script>
const SLIDES = {slides_json};
let i = 0;
const deck = document.getElementById('deck');
SLIDES.forEach((s, idx) => {{
  const d = document.createElement('div');
  d.className = 'slide' + (s.cover ? ' cover' : '') + (idx===0?' active':'');
  let h = '<h2>' + esc(s.title) + '</h2>';
  if (s.subtitle) h += '<div class="sub">' + esc(s.subtitle) + '</div>';
  if (s.body.length) h += '<ul>' + s.body.map(b => '<li>' + esc(b) + '</li>').join('') + '</ul>';
  d.innerHTML = h; deck.appendChild(d);
}});
function esc(s) {{ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}
function show(n) {{
  document.querySelectorAll('.slide').forEach(s=>s.classList.remove('active'));
  i = (n+SLIDES.length)%SLIDES.length;
  document.querySelectorAll('.slide')[i].classList.add('active');
  document.getElementById('bar').style.width = ((i+1)/SLIDES.length*100)+'%';
  document.getElementById('pg').textContent = (i+1)+' / '+SLIDES.length;
}}
document.addEventListener('keydown', e => {{
  if (e.key==='ArrowRight'||e.key===' ') {{ e.preventDefault(); show(i+1); }}
  else if (e.key==='ArrowLeft') show(i-1);
}});
show(0);
</script></body></html>
"""


def _write_html(kg, rows, out_dir: Path, kg_id: str) -> Path:
    slides = _slides_data(kg, rows)
    slides_json = json.dumps(slides, ensure_ascii=False).replace("</", "<\\/")
    doc = _HTML.format(subject=html.escape(kg.subject_id), slides_json=slides_json)
    fp = out_dir / f"slides-{kg_id}.html"
    fp.write_text(doc, encoding="utf-8")
    return fp


def _write_pptx(kg, rows, out_dir: Path, kg_id: str) -> Path:
    from pptx import Presentation

    prs = Presentation()
    # 封面
    cover = prs.slides.add_slide(prs.slide_layouts[0])
    cover.shapes.title.text = kg.subject_id
    cover.placeholders[1].text = f"共 {len(rows)} 个概念 · 自动生成"
    for r in rows:
        full = r.full_json or {}
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = r.name_primary or r.id
        tf = slide.placeholders[1].text_frame
        tf.text = f"定义：{r.definition or '（暂无）'}"
        if r.informal_description:
            tf.add_paragraph().text = f"通俗：{r.informal_description}"
        for e in (full.get("examples") or [])[:1]:
            if e.get("text"):
                tf.add_paragraph().text = f"例：{e['text']}"
    fp = out_dir / f"slides-{kg_id}.pptx"
    prs.save(str(fp))
    return fp


def generate_slides(
    *, db: RelationalStore, kg_id: str, out_dir: Path,
) -> ArtifactURI:
    """生成幻灯片。装了 python-pptx → .pptx；否则 → 自包含 HTML。"""
    kg, rows = load_sorted_concepts(db, kg_id)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if _HAS_PPTX:
        try:
            fp = _write_pptx(kg, rows, out_dir, kg_id)
            mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            logger.info("slides.done", kg_id=kg_id, fmt="pptx", slides=len(rows) + 1, file=str(fp))
            return ArtifactURI(uri=f"file:///{fp.as_posix()}", mime_type=mime,
                               size_bytes=fp.stat().st_size)
        except Exception as exc:  # noqa: BLE001 — pptx 失败回退 HTML
            logger.warning("slides.pptx_failed_fallback_html", error=str(exc))

    fp = _write_html(kg, rows, out_dir, kg_id)
    logger.info("slides.done", kg_id=kg_id, fmt="html", slides=len(rows) + 1, file=str(fp))
    return ArtifactURI(uri=f"file:///{fp.as_posix()}", mime_type="text/html",
                       size_bytes=fp.stat().st_size)
