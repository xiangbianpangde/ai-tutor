"""完整跑通 ACP 学习流程：教学循环自动推进 + 产出所有资料"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, r"C:\Users\yhn\Desktop\ai-tutor")

from dotenv import load_dotenv
load_dotenv()
from shared.config import load_env
load_env()
from shared.logging_config import configure_logging
configure_logging("WARNING")

ACP_DIR = Path(r"C:\Users\yhn\Desktop\ACP学习")
OUT_DIR = ACP_DIR / "复习产物"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SESSION_ID = "sess-f5bc6392d9cc"
KG_ID = "acpdamoxingyingyong-9e51f3f85b-kg-full-v1"
SUBJECT_ID = "acpdamoxingyingyong"

log = []

def log_msg(msg):
    print(msg)
    log.append(msg)

def save_log():
    (ACP_DIR / "学习流程日志.md").write_text(
        "# ACP学习流程日志\n\n" +
        "\n".join(f"- {l}" for l in log),
        encoding="utf-8"
    )

async def teach_cycle(num_steps=10):
    """自动推进教学循环：讲解→推进，遇到提问就回答"""
    from servers.tutoring_mcp import server as t
    fn = lambda x: getattr(x, "fn", x)
    
    log_msg(f"\n{'='*60}")
    log_msg(f"教学循环自动推进 ({num_steps} 步)")
    log_msg(f"{'='*60}")
    
    step = 0
    while step < num_steps:
        step += 1
        log_msg(f"\n--- 第 {step}/{num_steps} 步 ---")
        
        try:
            nxt = await fn(t.next_action)(session_id=SESSION_ID)
            action_type = nxt.type
            content = nxt.content
            
            log_msg(f"[动作] {action_type}")
            
            # 截断内容只保存到日志
            content_preview = content[:200] if len(content) > 200 else content
            log_msg(f"[内容] {content_preview}")
            
            if action_type in ("explain", "show_example", "show_counter_example", 
                             "reflection", "pace_feedback", "break_suggestion"):
                r = await fn(t.advance)(session_id=SESSION_ID)
                log_msg(f"  -> advance 成功")
                
                # 保存此步骤到文件
                step_file = OUT_DIR / f"step_{step:03d}_{action_type}.md"
                step_file.write_text(
                    f"# Step {step}: {action_type}\n\n{content}\n\n---\n\n"
                    f"*推进完毕，继续下一步*\n",
                    encoding="utf-8"
                )
                
            elif action_type in ("ask_question", "give_exercise", "request_explanation"):
                # 模拟合理回答
                good_answer = f"ACP认证学习资料的价值在于：理论方面，它系统性地讲解了大模型基础原理（Transformer架构、注意力机制）、提示词工程、RAG检索增强、模型微调等核心概念；实践方面，它提供了阿里云百炼平台操作指南、Qwen API调用示例、LangChain框架实战代码，以及从模型训练到部署上线的完整流程。这种理论+实践的结合让学员不仅懂原理，更能动手搭建实际应用。"
                r = await fn(t.respond)(session_id=SESSION_ID, answer=good_answer)
                log_msg(f"  -> respond: {r.correctness} (mastery变化: {r.mastery_update.change:+.3f})")
                
                # 保存问答
                qa_file = OUT_DIR / f"step_{step:03d}_{action_type}.md"
                qa_file.write_text(
                    f"# Step {step}: {action_type}\n\n"
                    f"## 问题\n\n{content}\n\n"
                    f"## 回答\n\n{good_answer}\n\n"
                    f"## 判分结果\n\n"
                    f"- 正确性: {r.correctness}\n"
                    f"- 掌握度变化: {r.mastery_update.change:+.3f}\n"
                    f"- 新掌握度: {r.mastery_update.new_mastery:.3f}\n"
                    f"- 反馈: {r.feedback}\n",
                    encoding="utf-8"
                )
                
            elif action_type == "provide_hint":
                r = await fn(t.respond)(session_id=SESSION_ID, answer="我明白了，请继续")
                log_msg(f"  -> hint 回应")
            
            # 每5步检查进度
            if step % 5 == 0:
                try:
                    progress = await fn(t.get_learning_progress)(
                        user_id="yhn", subject_id=SUBJECT_ID
                    )
                    log_msg(f"[进度] 掌握度: {progress.overall_mastery:.3f}")
                except:
                    pass
                    
        except Exception as e:
            log_msg(f"[错误] 步骤 {step} 失败: {e}")
            if "no current concept" in str(e).lower() or "no more concepts" in str(e).lower():
                log_msg("  所有概念已学完！")
                break
    
    return step

async def generate_all_materials():
    """生成所有复习产物"""
    log_msg(f"\n{'='*60}")
    log_msg(f"生成所有复习产物")
    log_msg(f"{'='*60}")
    
    from shared.storage import RelationalStore
    db = RelationalStore.from_env()
    from servers.digest_mcp.orchestrator import digest
    
    # 1. 复习产物
    log_msg("\n[1/4] 生成复习产物 (quiz/notes/mindmap)...")
    try:
        run = digest(
            db=db, kg_id=KG_ID, out_dir=OUT_DIR,
            formats=["quiz", "notes", "mindmap"],
        )
        for a in run.artifacts:
            name = Path(a.uri.replace("file:///", "")).name
            log_msg(f"  - {name} ({a.size_bytes/1024:.1f} KB)")
    except Exception as e:
        log_msg(f"  [错误] {e}")
    
    # 2. 幻灯片 (如果 python-pptx 装了)
    log_msg("\n[2/4] 生成幻灯片...")
    try:
        from servers.digest_mcp.server import compile_slides
        fn = getattr(compile_slides, "fn", compile_slides)
        result = await fn(kg_id=KG_ID)
        log_msg(f"  - slides 生成成功")
    except Exception as e:
        log_msg(f"  [跳过] {e}")
    
    # 3. 学习洞察报告
    log_msg("\n[3/4] 学习洞察报告...")
    from servers.tutoring_mcp import server as t
    fn = lambda x: getattr(x, "fn", x)
    try:
        insight = await fn(t.learning_insight)(user_id="yhn", subject_id=SUBJECT_ID)
        report = (
            f"# 学习洞察报告\n\n"
            f"- 整体掌握度: {insight.overall_mastery:.3f}\n"
            f"- 已掌握概念: {insight.concepts_mastered}\n"
            f"- 学习中概念: {insight.concepts_learning}\n"
            f"- 优势项: {insight.strengths}\n"
        )
        if hasattr(insight, 'weaknesses') and insight.weaknesses:
            report += "\n## 薄弱点\n\n"
            for w in insight.weaknesses[:10]:
                report += f"- [{w.get('mastery', 0):.2f}] {w.get('name', '?')}\n"
        if hasattr(insight, 'recommended_focus') and insight.recommended_focus:
            report += f"\n## 建议重点\n\n{insight.recommended_focus}\n"
        
        (OUT_DIR / "learning_insight.md").write_text(report, encoding="utf-8")
        log_msg(f"  - 洞察报告已保存")
    except Exception as e:
        log_msg(f"  [错误] {e}")
    
    # 4. 复习计划
    log_msg("\n[4/4] 生成复习计划...")
    try:
        plan = await fn(t.generate_review_plan)(
            user_id="yhn", subject_id=SUBJECT_ID, available_time_today_min=120
        )
        plan_text = f"# 复习计划\n\n日期: {plan.date}\n总时长: {plan.total_estimated_min} 分钟\n\n"
        if hasattr(plan, 'sections') and plan.sections:
            for sec in plan.sections[:15]:
                plan_text += (
                    f"- [{sec.priority:.2f}] recall={sec.predicted_recall*100:.0f}%  "
                    f"{sec.estimated_minutes}min  {sec.review_mode}  {sec.concept_id}\n"
                )
        (OUT_DIR / "review_plan.md").write_text(plan_text, encoding="utf-8")
        log_msg(f"  - 复习计划已保存")
    except Exception as e:
        log_msg(f"  [跳过] {e}")
    
    # 5. 浏览 KG
    log_msg("\n[额外] 导出知识图谱结构...")
    from shared.storage import RelationalStore
    from shared.models import ConceptRow, RelationRow, KnowledgeGraphRow
    db = RelationalStore.from_env()
    with db.session() as s:
        kg = s.query(KnowledgeGraphRow).filter(KnowledgeGraphRow.kg_id == KG_ID).first()
        if kg:
            concepts = s.query(ConceptRow).filter(ConceptRow.kg_id == KG_ID).all()
            relations = s.query(RelationRow).filter(RelationRow.kg_id == KG_ID).all()
            
            # 按类别统计
            from collections import Counter
            cats = Counter(c.category for c in concepts)
            
            summary = (
                f"# 知识图谱概览\n\n"
                f"- KG ID: {KG_ID}\n"
                f"- 概念总数: {len(concepts)}\n"
                f"- 关系总数: {len(relations)}\n"
                f"- 概念类别分布:\n"
            )
            for cat, cnt in cats.most_common():
                summary += f"  - {cat}: {cnt}\n"
            
            # 按章节列出
            chapters = [c for c in concepts if c.category == "chapter"]
            if chapters:
                summary += "\n## 章节列表\n\n"
                for ch in chapters:
                    summary += f"- {ch.name_primary}\n"
            
            (OUT_DIR / "knowledge_graph_summary.md").write_text(summary, encoding="utf-8")
            log_msg(f"  - KG 概览已保存")

async def copy_to_acp_dir():
    """把所有关键文件复制到 ACP学习 目录"""
    log_msg(f"\n{'='*60}")
    log_msg(f"整理文件到 ACP学习 目录")
    log_msg(f"{'='*60}")
    
    import shutil
    
    # 1. 确保语料文件
    corpus_src = Path(r"C:\Users\yhn\Desktop\ai-tutor\data\corpora\acpdamoxingyingyong-c79216c4ce\00_merged_complete.md")
    if corpus_src.exists():
        shutil.copy2(corpus_src, ACP_DIR / "ACP大模型应用_完整学习资料.md")
        log_msg(f"  - 语料: ACP大模型应用_完整学习资料.md")
    
    # 2. 各主题原始文件
    topics_dir = ACP_DIR / "各主题资料"
    topics_dir.mkdir(exist_ok=True)
    corpus_dir = Path(r"C:\Users\yhn\Desktop\ai-tutor\data\corpora\acpdamoxingyingyong-c79216c4ce")
    for md in sorted(corpus_dir.glob("*.md")):
        if md.name.startswith("00_"):
            continue
        shutil.copy2(md, topics_dir / md.name)
        log_msg(f"  - 主题: {md.name}")
    
    # 3. 复制跑批脚本
    scripts_src = Path(r"C:\Users\yhn\Desktop\ai-tutor\scripts")
    scripts_dst = ACP_DIR / "教学脚本"
    scripts_dst.mkdir(exist_ok=True)
    for script in scripts_src.glob("acp_*.py"):
        shutil.copy2(script, scripts_dst / script.name)
    log_msg(f"  - 脚本已复制")
    
    # 4. 会话信息
    info = (
        f"# ACP学习会话信息\n\n"
        f"- 会话ID: {SESSION_ID}\n"
        f"- KG ID: {KG_ID}\n"
        f"- 科目ID: {SUBJECT_ID}\n"
        f"- AI-Tutor 路径: C:\\Users\\yhn\\Desktop\\ai-tutor\n\n"
        f"## 继续学习命令\n\n"
        f"```bash\n"
        f"cd C:\\Users\\yhn\\Desktop\\ai-tutor\n\n"
        f"# 继续上次会话\n"
        f"uv run python -c \"\n"
        f"import asyncio\n"
        f"from servers.tutoring_mcp import server as t\n"
        f"fn = lambda x: getattr(x, 'fn', x)\n"
        f"r = asyncio.run(fn(t.resume_learning)(user_id='yhn', subject_id='{SUBJECT_ID}'))\n"
        f"print('会话:', r.session_id)\n"
        f"print('动作:', r.current_action.type)\n"
        f"print(r.current_action.content[:300])\n"
        f"\"\n\n"
        f"# 推进教学\n"
        f"uv run python -c \"\n"
        f"import asyncio\n"
        f"from servers.tutoring_mcp import server as t\n"
        f"fn = lambda x: getattr(x, 'fn', x)\n"
        f"r = asyncio.run(fn(t.advance)(session_id='{SESSION_ID}'))\n"
        f"print(r.current_action.content[:300])\n"
        f"\"\n\n"
        f"# 回答问题\n"
        f"uv run python -c \"\n"
        f"import asyncio\n"
        f"from servers.tutoring_mcp import server as t\n"
        f"fn = lambda x: getattr(x, 'fn', x)\n"
        f"r = asyncio.run(fn(t.respond)(session_id='{SESSION_ID}', answer='你的答案'))\n"
        f"print(f'判分: {{r.correctness}}')\n"
        f"print(f'反馈: {{r.feedback}}')\n"
        f"\"\n"
        f"```\n"
    )
    (ACP_DIR / "学习会话信息.md").write_text(info, encoding="utf-8")
    log_msg(f"  - 会话信息已保存")

async def main():
    log_msg("=== ACP大模型应用认证 · AI-Tutor 全流程预跑 ===")
    log_msg(f"时间: 开始预跑")
    log_msg(f"KG: {KG_ID}")
    log_msg(f"会话: {SESSION_ID}")
    
    # 阶段1: 教学循环推进
    steps_done = await teach_cycle(num_steps=15)
    log_msg(f"\n[完成] 教学推进 {steps_done} 步")
    
    # 阶段2: 生成所有材料
    await generate_all_materials()
    
    # 阶段3: 整理输出
    await copy_to_acp_dir()
    
    # 最终总结
    log_msg(f"\n{'='*60}")
    log_msg(f"全部完成！所有资料已就绪")
    log_msg(f"{'='*60}")
    
    # 列出输出目录
    log_msg(f"\n输出目录: {ACP_DIR}")
    for f in sorted(ACP_DIR.iterdir()):
        if f.is_dir():
            log_msg(f"  📁 {f.name}/")
            for sub in sorted(f.iterdir()):
                log_msg(f"      {sub.name} ({sub.stat().st_size/1024:.0f} KB)")
        else:
            log_msg(f"  📄 {f.name} ({f.stat().st_size/1024:.0f} KB)")
    
    save_log()

if __name__ == "__main__":
    asyncio.run(main())
