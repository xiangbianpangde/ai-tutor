"""simulation generator — 自包含 HTML 交互闪卡。

每个 concept 一张可翻转卡（正面 = 名称，背面 = 定义 + 通俗解释）。
纯内联 CSS/JS，无 CDN / 无外部依赖 → 离线双击即可在浏览器打开。
键盘：← / → 切换，空格翻转。

后续可加：拖拽连线题、概念关系图嵌入、答题计分。
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from shared.logging_config import get_logger
from shared.schemas import ArtifactURI
from shared.storage import RelationalStore

from ._kg_read import load_sorted_concepts

logger = get_logger("digest_mcp.simulation")


def _build_cards(rows) -> list[dict]:
    cards: list[dict] = []
    for r in rows:
        full = r.full_json or {}
        examples = [e.get("text", "") for e in (full.get("examples") or []) if e.get("text")]
        cards.append({
            "id": r.id,
            "name": r.name_primary or r.id,
            "definition": r.definition or "（暂无定义）",
            "informal": r.informal_description or "",
            "examples": examples[:2],
            "confidence": round(float(r.confidence or 0), 2),
        })
    return cards


_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>交互闪卡 — {subject}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         margin: 0; background: #0f172a; color: #e2e8f0;
         display: flex; flex-direction: column; align-items: center;
         min-height: 100vh; padding: 24px; }}
  h1 {{ font-size: 18px; font-weight: 600; color: #94a3b8; }}
  #progress {{ color: #64748b; font-size: 14px; margin-bottom: 16px; }}
  #card {{ width: min(560px, 92vw); min-height: 320px; perspective: 1200px;
          cursor: pointer; }}
  .inner {{ position: relative; width: 100%; min-height: 320px;
           transition: transform .5s; transform-style: preserve-3d; }}
  .flipped .inner {{ transform: rotateY(180deg); }}
  .face {{ position: absolute; width: 100%; min-height: 320px; backface-visibility: hidden;
          border-radius: 16px; padding: 32px; display: flex; flex-direction: column;
          justify-content: center; box-shadow: 0 10px 40px rgba(0,0,0,.4); }}
  .front {{ background: linear-gradient(135deg,#1e3a8a,#1e40af); }}
  .back {{ background: linear-gradient(135deg,#134e4a,#115e59); transform: rotateY(180deg);
          justify-content: flex-start; overflow-y: auto; }}
  .name {{ font-size: 28px; font-weight: 700; text-align: center; }}
  .hint {{ margin-top: 16px; text-align: center; color: #93c5fd; font-size: 13px; }}
  .label {{ color: #5eead4; font-size: 13px; font-weight: 600; margin-top: 12px; }}
  .text {{ font-size: 16px; line-height: 1.7; margin-top: 4px; }}
  .ex {{ font-size: 14px; color: #cbd5e1; margin-top: 4px; }}
  #nav {{ margin-top: 20px; display: flex; gap: 12px; align-items: center; }}
  button {{ background: #334155; color: #e2e8f0; border: 0; border-radius: 8px;
           padding: 10px 20px; font-size: 15px; cursor: pointer; }}
  button:hover {{ background: #475569; }}
  #conf {{ position: absolute; top: 12px; right: 16px; font-size: 12px; color: #64748b; }}
</style>
</head>
<body>
<h1>📇 交互闪卡 · {subject}</h1>
<div id="progress"></div>
<div id="card"><div class="inner">
  <div class="face front"><div class="name" id="front-name"></div>
    <div class="hint">点击 / 空格 翻面看定义</div></div>
  <div class="face back"><span id="conf"></span>
    <div class="label">定义</div><div class="text" id="back-def"></div>
    <div id="back-extra"></div></div>
</div></div>
<div id="nav">
  <button onclick="prev()">← 上一张</button>
  <button onclick="flip()">翻面</button>
  <button onclick="next()">下一张 →</button>
</div>
<script>
const CARDS = {cards_json};
let i = 0;
const cardEl = document.getElementById('card');
function render() {{
  const c = CARDS[i];
  document.getElementById('front-name').textContent = c.name;
  document.getElementById('back-def').textContent = c.definition;
  document.getElementById('conf').textContent = '置信度 ' + c.confidence;
  let extra = '';
  if (c.informal) extra += '<div class="label">通俗解释</div><div class="text">' + esc(c.informal) + '</div>';
  if (c.examples && c.examples.length) {{
    extra += '<div class="label">例子</div>';
    c.examples.forEach(e => extra += '<div class="ex">· ' + esc(e) + '</div>');
  }}
  document.getElementById('back-extra').innerHTML = extra;
  cardEl.classList.remove('flipped');
  document.getElementById('progress').textContent = (i+1) + ' / ' + CARDS.length;
}}
function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}
function flip() {{ cardEl.classList.toggle('flipped'); }}
function next() {{ i = (i+1) % CARDS.length; render(); }}
function prev() {{ i = (i-1+CARDS.length) % CARDS.length; render(); }}
cardEl.onclick = flip;
document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight') next();
  else if (e.key === 'ArrowLeft') prev();
  else if (e.key === ' ') {{ e.preventDefault(); flip(); }}
}});
render();
</script>
</body>
</html>
"""


def generate_simulation(
    *, db: RelationalStore, kg_id: str, out_dir: Path,
) -> ArtifactURI:
    """生成自包含 HTML 交互闪卡，返回 ArtifactURI。"""
    kg, rows = load_sorted_concepts(db, kg_id)
    cards = _build_cards(rows)
    if not cards:
        cards = [{"id": "", "name": "（此 KG 暂无概念）", "definition": "请先构建知识图谱。",
                  "informal": "", "examples": [], "confidence": 0.0}]

    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"simulation-{kg_id}.html"

    # 把 JSON 内联进 <script> 时，必须转义 </ 防止 </script> 提前闭合脚本块（XSS）。
    # <\/ 在 JSON 字符串里合法，解析回来仍是 </。
    cards_json = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")
    doc = _TEMPLATE.format(
        subject=html.escape(kg.subject_id),
        cards_json=cards_json,
    )
    file_path.write_text(doc, encoding="utf-8")

    logger.info("simulation.done", kg_id=kg_id, cards=len(cards), file=str(file_path))
    return ArtifactURI(
        uri=f"file:///{file_path.as_posix()}",
        mime_type="text/html",
        size_bytes=file_path.stat().st_size,
    )
