"""Step 3: 创建用户 + 摸底 + 开始学习"""
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
configure_logging("INFO")

async def main():
    kg_id = "acpdamoxingyingyong-9e51f3f85b-kg-full-v1"
    subject_slug = "acpdamoxingyingyong"
    
    print("=" * 60)
    print("Step 3: 初始化 + 摸底 + 开课")
    print(f"  kg_id = {kg_id}")
    print("=" * 60)
    
    from shared.storage import RelationalStore
    db = RelationalStore.from_env()
    
    # 1. 创建用户
    from shared.models import User, Subject
    with db.session() as s:
        user = s.query(User).filter(User.id == "yhn").first()
        if not user:
            s.add(User(id="yhn", display_name="YHN"))
            print("[用户] 创建用户: yhn")
        else:
            print("[用户] 用户已存在: yhn")
        
        # 创建/更新 subject 关联
        subj = s.query(Subject).filter(Subject.id == subject_slug).first()
        if not subj:
            s.add(Subject(id=subject_slug, user_id="yhn", display_name="ACP大模型应用"))
            print(f"[科目] 创建科目: {subject_slug}")
        else:
            print(f"[科目] 科目已存在: {subject_slug}")
        
        # 关联 KG
        subj = s.query(Subject).filter(Subject.id == subject_slug).first()
        subj.kg_id = kg_id
        s.commit()
        print(f"[KG关联] subject.kg_id = {subj.kg_id}")
    
    # 2. 查询 KG 概况
    from shared.models import ConceptRow, RelationRow
    with db.session() as s:
        concepts = s.query(ConceptRow).filter(ConceptRow.kg_id == kg_id).all()
        edges = s.query(RelationRow).filter(RelationRow.kg_id == kg_id).all()
        print(f"\n[KG概况] 概念: {len(concepts)}, 关系: {len(edges)}")
        
        # 列出所有章节级概念
        chapters = [c for c in concepts if c.category == "chapter"]
        print(f"  章节数: {len(chapters)}")
        for ch in chapters[:10]:
            print(f"    [章] {ch.name_primary[:40]}")
        if len(chapters) > 10:
            print(f"    ... 还有 {len(chapters)-10} 个章节")
    
    # 3. 摸底测试 - 出题
    print("\n[摸底] 进行冷启动摸底...")
    from servers.tutoring_mcp import server as tserver
    def fn(tool):
        return getattr(tool, "fn", tool)
    
    try:
        probe = await fn(tserver.cold_start_probe)(
            user_id="yhn",
            subject_id=subject_slug,
            num_questions=5,
        )
        print(f"  出题数: {len(probe.questions)}")
        for i, q in enumerate(probe.questions):
            print(f"    Q{i+1}: {q.content[:60]}...")
    except Exception as e:
        print(f"  摸底失败 (可跳过): {e}")
    
    # 4. 开始学习会话
    print("\n[开课] 开始学习会话 (goal=48h_sprint)...")
    try:
        session = await fn(tserver.start_learning_session)(
            user_id="yhn",
            subject_id=subject_slug,
            goal="48h_sprint",
        )
        print(f"  会话ID: {session.session_id}")
        print(f"  教学计划概念数: {session.teaching_plan.get('total_concepts', 'N/A')}")
        print(f"  首个动作: {session.current_action.type}")
        # content 可能很长，截断
        content = str(session.current_action.content)
        if len(content) > 120:
            content = content[:120] + "..."
        print(f"  内容: {content}")
        
        # 保存 session_id
        with open(r"C:\Users\yhn\Desktop\ACP学习\.last_session_id", "w") as f:
            f.write(session.session_id)
        print(f"\n[保存] session_id 已保存")
    except Exception as e:
        print(f"  开课失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Step 3 完成!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
