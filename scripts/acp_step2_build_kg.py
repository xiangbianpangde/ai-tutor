"""Step 2: 构建知识图谱"""
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

from servers.knowledge_mcp import server as k
from shared.storage import RelationalStore

def fn(tool):
    return getattr(tool, "fn", tool)

async def main():
    corpus_id = "acpdamoxingyingyong-c79216c4ce"
    
    print("=" * 60)
    print("Step 2: 构建知识图谱 (depth=full)")
    print(f"  corpus_id = {corpus_id}")
    print("=" * 60)
    
    # 1. 查询语料库信息
    db = RelationalStore.from_env()
    from shared.models import Corpus
    with db.session() as s:
        corpus = s.query(Corpus).filter(Corpus.id == corpus_id).first()
        if corpus:
            print(f"\n[语料库] 找到 corpus: {corpus.id}")
        else:
            print(f"\n[警告] corpus {corpus_id} 不在数据库中")
    
    # 2. 构建知识图谱 (depth=full, 包含 LLM 富化、时长校准、难度校准)
    print(f"\n[建图] 开始构建知识图谱 (depth=full, 会调用 DeepSeek)...")
    print(f"      这可能要几分钟，请耐心等待...\n")
    
    try:
        kg_result = await fn(k.build_knowledge_graph)(
            corpus_id=corpus_id,
            depth="full",
        )
        
        print(f"\n[完成] 知识图谱构建成功!")
        print(f"   kg_id: {kg_result.kg_id}")
        
        # 质量报告
        quality = kg_result.quality_report
        print(f"   Subject slug: {kg_result.kg_id.split('-')[0]}")
        print(f"   概念数: {quality.total_concepts}")
        print(f"   关系数: {quality.total_relations}")
        print(f"   平均置信度: {quality.avg_confidence:.3f}")
        print(f"   章节覆盖率: {quality.chapter_coverage:.1%}")
        
        # 如果有低置信概念，列出来
        if hasattr(quality, 'low_confidence_concepts') and quality.low_confidence_concepts:
            print(f"\n   低置信概念 ({len(quality.low_confidence_concepts)}):")
            for c in quality.low_confidence_concepts[:5]:
                print(f"     - {c}")
        
        # 保存 kg_id 供后续使用
        kg_id_path = r"C:\Users\yhn\Desktop\ACP学习\.last_kg_id"
        with open(kg_id_path, "w") as f:
            f.write(kg_result.kg_id)
        print(f"\n[保存] kg_id 已保存到 {kg_id_path}")
        
    except Exception as e:
        print(f"\n[错误] 构建知识图谱失败: {e}")
        print("尝试 depth=toc (免 LLM，只抽章节结构)")
        print("\n[重试] depth=toc...\n")
        
        try:
            kg_result = await fn(k.build_knowledge_graph)(
                corpus_id=corpus_id,
                depth="toc",
            )
            print(f"\n[完成] TOC 知识图谱构建成功!")
            print(f"   kg_id: {kg_result.kg_id}")
        except Exception as e2:
            print(f"\n[错误] TOC 也失败: {e2}")

if __name__ == "__main__":
    asyncio.run(main())
