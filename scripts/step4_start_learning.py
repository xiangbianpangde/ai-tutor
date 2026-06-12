"""Step 4: 冷启动摸底 + 开课学习"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from servers.knowledge_mcp import server as k
from servers.tutoring_mcp import server as t

def fn(tool):
    return getattr(tool, "fn", tool)

async def main():
    subject_id = "tudeliantongxingyujuzhenbiaoshi"
    user_id = "yhn"
    
    print("=" * 60)
    print(f"Step 4: 开课学习")
    print(f"   subject_id = {subject_id}")
    print(f"   user_id    = {user_id}")
    print("=" * 60)
    
    # --- 4a: 冷启动摸底（推荐，省时间） ---
    print("\n--- 4a: 冷启动摸底 cold_start_probe ---")
    try:
        probe = await fn(t.cold_start_probe)(
            user_id=user_id,
            subject_id=subject_id,
            num_questions=5,
        )
        print(f"✅ 摸底题生成！共 {len(probe.questions)} 题")
        for q in probe.questions:
            print(f"   [{q.difficulty}] {q.question[:80]}...")
            print(f"      选项: {q.options}")
        
        # 用户需回答 → 这里先跳过，直接开课
        print("\n⚠  跳过 submit_cold_start（可在后续教学过程中逐步摸底）")
    except Exception as e:
        print(f"   ⚠ 冷启动跳过: {e}")
    
    # --- 4b: 开课 ---
    print("\n--- 4b: 开课 start_learning_session ---")
    session = await fn(t.start_learning_session)(
        user_id=user_id,
        subject_id=subject_id,
        goal="48h_sprint",
    )
    
    print(f"\n✅ 开课成功！")
    print(f"   session_id: {session.session_id}")
    print(f"   首动作类型: {session.current_action.type}")
    print(f"   内容: {session.current_action.content[:200]}...")
    
    # 保存 session_id
    with open("scripts/.last_session_id", "w") as f:
        f.write(session.session_id)
    print(f"\n➡  session_id 已保存到 scripts/.last_session_id")

if __name__ == "__main__":
    asyncio.run(main())
