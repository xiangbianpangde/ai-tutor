"""Step 4: 生成复习产物到 ACP学习目录"""
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
    kg_id = "acpdamoxingyingyong-9e51f3f85b-kg-full-v1"
    out_base = Path(r"C:\Users\yhn\Desktop\ACP学习")
    
    print("=" * 60)
    print("Step 4: 生成复习产物")
    print("=" * 60)
    
    from shared.storage import RelationalStore
    db = RelationalStore.from_env()
    
    from servers.digest_mcp.orchestrator import digest
    
    out_dir = out_base / "复习产物"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[产物] 输出目录: {out_dir}")
    print(f"[产物] 生成格式: quiz, notes, mindmap\n")
    
    try:
        run = digest(
            db=db,
            kg_id=kg_id,
            out_dir=out_dir,
            formats=["quiz", "notes", "mindmap"],
        )
        
        print(f"[完成] 产物生成完毕!")
        for a in run.artifacts:
            size = a.size_bytes / 1024
            name = Path(a.uri.replace("file:///", "")).name
            print(f"  [{a.mime_type:24s}] {size:6.1f} KB  {name}")
        
        if run.warnings:
            for w in run.warnings:
                print(f"  [警告] {w}")
        
        # 列出目录内容
        print(f"\n[目录] 复习产物文件:")
        for f in sorted(out_dir.iterdir()):
            size_kb = f.stat().st_size / 1024
            print(f"  {f.name:40s} {size_kb:7.1f} KB")
    
    except Exception as e:
        print(f"[错误] 生成产物失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
