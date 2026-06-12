"""获取当前会话的下一个教学动作"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from servers.tutoring_mcp import server as t

def fn(tool):
    return getattr(tool, "fn", tool)

async def main():
    session_id = "sess-def61dcc79a6"
    
    # 默认走 advance（讲解类动作后调用）
    action = sys.argv[1] if len(sys.argv) > 1 else "advance"
    answer = sys.argv[2] if len(sys.argv) > 2 else None
    
    if action == "advance":
        result = await fn(t.advance)(session_id=session_id)
        print(f"TYPE: {result.action.type}")
        print(f"CONTENT: {result.action.content}")
        print(f"CONCEPT: {result.action.concept_id}")
        if hasattr(result.action, 'question') and result.action.question:
            print(f"QUESTION: {result.action.question}")
    elif action == "respond":
        result = await fn(t.respond)(session_id=session_id, answer=answer)
        print(f"TYPE: {result.action.type}")
        print(f"CONTENT: {result.action.content}")
        print(f"FEEDBACK: {result.feedback}" if hasattr(result, 'feedback') else "")
    elif action == "status":
        result = await fn(t.next_action)(session_id=session_id)
        print(f"TYPE: {result.type}")
        print(f"CONTENT: {result.content}")

if __name__ == "__main__":
    asyncio.run(main())
