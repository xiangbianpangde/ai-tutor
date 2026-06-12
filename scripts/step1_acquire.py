"""Step 1: 采集 PDF → 建语料库"""
import asyncio
import sys
import os

# 加项目根到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from servers.knowledge_mcp import server as k

def fn(tool):
    return getattr(tool, "fn", tool)

async def main():
    print("=" * 60)
    print("Step 1: 采集 PDF → acquire_subject")
    print("=" * 60)

    result = await fn(k.acquire_subject)(
        subject="图的连通性与矩阵表示",
        sources=[{
            "type": "file",
            "uri": r"C:/Users/yhn/Desktop/v2026 5.2-3图的连通性和矩阵表示.pdf"
        }],
        user_id="yhn",
    )

    print(f"\n✅ 采集完成！")
    print(f"   corpus_id: {result.corpus_id}")
    print(f"   subject: {result.subject}")
    print(f"   source_count: {result.source_count}")

    # 保存 corpus_id 供后续步骤使用
    with open("scripts/.last_corpus_id", "w") as f:
        f.write(result.corpus_id)
    print(f"\n➡  corpus_id 已保存到 scripts/.last_corpus_id")

if __name__ == "__main__":
    asyncio.run(main())
