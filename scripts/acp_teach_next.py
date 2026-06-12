"""教学循环 — 推进下一步并展示内容"""
import asyncio
import sys
sys.path.insert(0, r"C:\Users\yhn\Desktop\ai-tutor")
from dotenv import load_dotenv
import json

load_dotenv()
from shared.config import load_env
load_env()
from shared.logging_config import configure_logging
configure_logging("WARNING")

async def main():
    session_id = "sess-f5bc6392d9cc"
    
    from servers.tutoring_mcp import server as t
    fn = lambda x: getattr(x, "fn", x)
    
    # 1. 获取当前动作
    print("=== 获取下一教学动作 ===")
    try:
        nxt = await fn(t.next_action)(session_id=session_id)
        print(f"动作类型: {nxt.type}")
        print(f"内容:")
        print(nxt.content)
        print(f"\n---")
    except Exception as e:
        print(f"next_action 失败: {e}")
    
    # 2. 如果是讲解类型，自动推进
    if nxt.type in ("explain", "show_example", "show_counter_example", "reflection", "pace_feedback", "break_suggestion"):
        print(f"\n=== 自动推进 (advance) ===")
        r = await fn(t.advance)(session_id=session_id)
        if hasattr(r, 'current_action') and r.current_action:
            print(f"下一动作: {r.current_action.type}")
            print(f"内容预览: {str(r.current_action.content)[:200]}")
    elif nxt.type in ("ask_question", "give_exercise", "request_explanation", "provide_hint"):
        print(f"\n=== 这是问答步骤 ===")
        print(f"请回答以上问题，我会帮你提交")

if __name__ == "__main__":
    asyncio.run(main())
