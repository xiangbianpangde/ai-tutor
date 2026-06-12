"""Step 3: 建知识图谱"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from servers.knowledge_mcp import server as k

def fn(tool):
    return getattr(tool, "fn", tool)

async def main():
    corpus_id = "tudeliantongxingyujuzhenbiaoshi-694e9e5e0d"
    
    print("=" * 60)
    print("Step 3: 建知识图谱 → build_knowledge_graph")
    print(f"   corpus_id = {corpus_id}")
    print("=" * 60)
    
    print("\n⏳ 正在建图（depth=full，含 LLM 概念富化）...")
    result = await fn(k.build_knowledge_graph)(
        corpus_id=corpus_id,
        depth="full",
    )
    
    print(f"\n✅ 建图完成！")
    print(f"   kg_id: {result.kg_id}")
    print(f"   triples_count: {result.triples_count}")

if __name__ == "__main__":
    asyncio.run(main())
