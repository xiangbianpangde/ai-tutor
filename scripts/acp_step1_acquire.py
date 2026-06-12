"""Step 1: 采集 ACP大模型应用 web 资料"""
import asyncio
import sys
import os
from pathlib import Path

# 加项目根到路径
sys.path.insert(0, r"C:\Users\yhn\Desktop\ai-tutor")

from dotenv import load_dotenv
load_dotenv()

from servers.knowledge_mcp import server as k
from shared.logging_config import configure_logging
configure_logging("INFO")

def fn(tool):
    return getattr(tool, "fn", tool)

async def main():
    print("=" * 60)
    print("Step 1: 采集 ACP大模型应用 资料")
    print("=" * 60)
    
    # 用多个 web 主题覆盖考试范围
    topics = [
        "阿里云ACP大模型应用认证 考试大纲",
        "阿里云百炼大模型平台 使用指南",
        "大模型基础理论 Transformer 架构",
        "提示词工程 Prompt Engineering 最佳实践",
        "RAG检索增强生成 原理与实践",
        "大模型微调 Fine-tuning LoRA QLoRA",
        "AI Agent 智能体 架构设计",
        "大模型部署 推理优化 vLLM",
        "阿里云通义千问 Qwen API使用",
        "大模型应用开发 LangChain 框架"
    ]
    
    # 合并成一个采集
    sources = [{"type": "web", "uri": topic} for topic in topics]
    
    print(f"\n[采集] 将采集 {len(topics)} 个主题:")
    for t in topics:
        print(f"   - {t}")
    
    result = await fn(k.acquire_subject)(
        subject="ACP大模型应用",
        sources=sources,
        user_id="yhn",
    )
    
    print(f"\n[完成] 采集结束!")
    print(f"   corpus_id: {result.corpus_id}")
    print(f"   subject: {result.subject}")
    print(f"   source_count: {result.source_count}")
    print(f"   章节数: {result.total_chapters}")
    print(f"   小节数: {result.total_sections}")

    # 保存 corpus_id
    corpus_id_path = r"C:\Users\yhn\Desktop\ACP学习\.last_corpus_id"
    with open(corpus_id_path, "w") as f:
        f.write(result.corpus_id)
    print(f"\n[保存] corpus_id 已保存到 {corpus_id_path}")

if __name__ == "__main__":
    asyncio.run(main())
