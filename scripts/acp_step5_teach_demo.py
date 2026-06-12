"""Step 5: 教学循环演示 — 推进学习"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\yhn\Desktop\ai-tutor")

from dotenv import load_dotenv
load_dotenv()

from shared.config import load_env
load_env()

from shared.logging_config import configure_logging
configure_logging("INFO")

async def main():
    session_id = "sess-f5bc6392d9cc"
    subject_id = "acpdamoxingyingyong"
    
    print("=" * 60)
    print("Step 5: 教学循环演示")
    print("=" * 60)
    
    from servers.tutoring_mcp import server as tserver
    def fn(tool):
        return getattr(tool, "fn", tool)
    
    # 1. 查看当前进度
    print("\n[进度] 获取学习进度...")
    try:
        progress = await fn(tserver.get_learning_progress)(
            user_id="yhn",
            subject_id=subject_id,
        )
        print(f"   掌握度: {progress.overall_mastery:.2%}")
        print(f"   已掌握: {progress.concepts_mastered}")
        print(f"   学习中: {progress.concepts_learning}")
    except Exception as e:
        print(f"   {e}")
    
    # 2. 推进一轮教学 (讲解 -> 继续)
    print("\n[教学] 推进教学循环 (3步)...\n")
    
    for i in range(3):
        print(f"  --- 第 {i+1} 步 ---")
        try:
            # 获取当前动作
            nxt = await fn(tserver.next_action)(session_id=session_id)
            print(f"  动作类型: {nxt.type}")
            content = str(nxt.content)[:150]
            print(f"  内容: {content}")
            
            if nxt.type in ("explain", "show_example", "show_counter_example", 
                          "reflection", "pace_feedback", "break_suggestion"):
                # 讲解类 -> advance
                print("  => advance (继续)")
                r = await fn(tserver.advance)(session_id=session_id)
                if hasattr(r, 'current_action') and r.current_action:
                    print(f"  下一动作: {r.current_action.type}")
            elif nxt.type in ("ask_question", "give_exercise", "request_explanation", "provide_hint"):
                # 问答类 -> respond
                print("  => respond (模拟作答)")
                r = await fn(tserver.respond)(
                    session_id=session_id,
                    answer="大模型应用是指基于预训练大语言模型开发的实际应用系统，包括文本生成、问答系统、智能客服等场景。"
                )
                print(f"  判分: {r.correctness}")
                if hasattr(r, 'feedback') and r.feedback:
                    fb = str(r.feedback)[:100]
                    print(f"  反馈: {fb}")
        except Exception as e:
            print(f"  步骤异常: {e}")
            break
    
    # 3. 学习洞察
    print("\n[洞察] 学习洞察报告...")
    try:
        insight = await fn(tserver.learning_insight)(
            user_id="yhn",
            subject_id=subject_id,
        )
        print(f"   整体掌握度: {insight.overall_mastery:.3f}")
        print(f"   掌握数/学习中: {insight.concepts_mastered}/{insight.concepts_learning}")
        if hasattr(insight, 'weaknesses') and insight.weaknesses:
            print(f"   薄弱点 ({len(insight.weaknesses)}):")
            for w in insight.weaknesses[:3]:
                print(f"     - {w.get('name', '?')}: {w.get('mastery', 0):.2f}")
    except Exception as e:
        print(f"   {e}")
    
    print("\n" + "=" * 60)
    print("教学循环演示完成!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
