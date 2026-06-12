"""合并 10 个主题语料为一个完整 markdown，重建 KG"""
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
    corpus_dir = Path(r"C:\Users\yhn\Desktop\ai-tutor\data\corpora\acpdamoxingyingyong-c79216c4ce")
    
    # 1. 列出所有 merged markdown 文件
    merged_mds = list(corpus_dir.glob("*.md"))
    print(f"找到 {len(merged_mds)} 个合并 markdown 文件:")
    for md in sorted(merged_mds):
        size_kb = md.stat().st_size / 1024
        print(f"   [{size_kb:6.1f} KB] {md.name}")
    
    # 2. 合并成一个完整的 markdown
    output_path = corpus_dir / "00_merged_complete.md"
    all_content = []
    all_content.append("# ACP大模型应用认证 完整学习资料\n\n")
    all_content.append("> 由 AI-Tutor research-tool 从 10 个主题采集合并\n\n")
    
    # 读取每个主题文件并合并
    total_chars = 0
    for md_file in sorted(merged_mds):
        if md_file.name == "00_merged_complete.md":
            continue
        content = md_file.read_text(encoding="utf-8", errors="replace")
        # 用主题文件名作为一级标题
        title = md_file.stem.replace("_", " ").replace("-", " ").strip()
        # 如果已经有 # 开头的内容，保留；否则添加
        if not content.startswith("#"):
            all_content.append(f"\n## {title}\n\n")
        all_content.append(content)
        all_content.append("\n\n---\n\n")
        total_chars += len(content)
    
    merged = "".join(all_content)
    output_path.write_text(merged, encoding="utf-8")
    
    total_kb = len(merged) / 1024
    print(f"\n[合并完成]")
    print(f"   输出: {output_path}")
    print(f"   总大小: {total_kb:.0f} KB")
    print(f"   总字符: {len(merged)}")
    
    # 3. 统计章节
    h1_count = sum(1 for line in merged.split("\n") if line.startswith("# "))
    h2_count = sum(1 for line in merged.split("\n") if line.startswith("## "))
    h3_count = sum(1 for line in merged.split("\n") if line.startswith("### "))
    print(f"   章节统计: H1={h1_count}  H2={h2_count}  H3={h3_count}")
    
    # 4. 清除旧的 KG 重新建图
    print("\n[建图] 重建知识图谱...")
    
    from shared.storage import RelationalStore
    db = RelationalStore.from_env()
    
    # 删除旧的 KG 记录
    with db.session() as s:
        from shared.models import Subject, KnowledgeGraphRow, ConceptRow, RelationRow
        # 找到并删除旧 KG
        old_kgs = s.query(KnowledgeGraphRow).filter(
            KnowledgeGraphRow.subject_id == "acpdamoxingyingyong"
        ).all()
        for kg in old_kgs:
            print(f"   删除旧 KG: {kg.kg_id}")
            s.query(ConceptRow).filter(ConceptRow.kg_id == kg.kg_id).delete()
            s.query(RelationRow).filter(RelationRow.kg_id == kg.kg_id).delete()
            s.delete(kg)
        
        # 清除 subject 关联
        subj = s.query(Subject).filter(Subject.id == "acpdamoxingyingyong").first()
        if subj:
            subj.kg_id = None
        s.commit()
    
    print("   旧 KG 已清除\n")
    
    # 现在调用 build_knowledge_graph - 但这需要重新acquire
    # 或者直接用 kg_builder 处理合并后的文件
    print("[方案] 用 acquire 重新采集合并文件")
    
    from servers.knowledge_mcp import server as k
    def fn(tool):
        return getattr(tool, "fn", tool)
    
    # 先采集这个合并文件作为 file 源
    result = await fn(k.acquire_subject)(
        subject="ACP大模型应用",
        sources=[{
            "type": "file",
            "uri": str(output_path),
        }],
        user_id="yhn",
    )
    print(f"\n[采集完成] corpus_id = {result.corpus_id}")
    
    # 用新的 corpus 建 KG
    kg_result = await fn(k.build_knowledge_graph)(
        corpus_id=result.corpus_id,
        depth="full",
    )
    
    print(f"\n[KG完成] kg_id = {kg_result.kg_id}")
    
    # 保存 kg_id
    kg_id_path = r"C:\Users\yhn\Desktop\ACP学习\.last_kg_id"
    with open(kg_id_path, "w") as f:
        f.write(kg_result.kg_id)
    print(f"   kg_id 已保存到 {kg_id_path}")

if __name__ == "__main__":
    asyncio.run(main())
