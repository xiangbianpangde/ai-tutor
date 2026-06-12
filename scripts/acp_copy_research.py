"""复制 research-tool 完整调研资料到 ACP学习目录"""
import shutil
import json
from pathlib import Path
from datetime import datetime

SRC = Path(r"C:\Users\yhn\Desktop\ai-tutor\data\corpora\acpdamoxingyingyong-c79216c4ce")
DST = Path(r"C:\Users\yhn\Desktop\ACP学习\调研资料")

def format_size(size):
    return f"{size/1024:.1f} KB"

def copy_tree(src, dst):
    """递归复制目录结构"""
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in src.iterdir():
        if item.is_dir():
            sub_dst = dst / item.name
            sub_dst.mkdir(parents=True, exist_ok=True)
            count += copy_tree(item, sub_dst)
        elif item.suffix in (".md", ".json"):
            try:
                shutil.copy2(item, dst / item.name)
                count += 1
            except:
                pass
    return count

def generate_report():
    """生成调研总结报告"""
    # 收集统计信息
    topics = sorted([d for d in SRC.iterdir() if d.is_dir()])
    merged_mds = sorted(SRC.glob("*.md"))
    
    report = []
    report.append("# ACP大模型应用认证 · 调研资料\n")
    report.append(f"> 由 research-tool 采集生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    report.append(f"> 采集引擎: Tavily + Yandex + httpx\n")
    report.append(f"> LLM: DeepSeek (概念富化/判分)\n\n")
    
    report.append("---\n\n## 总览\n\n")
    report.append(f"| 指标 | 数值 |\n|------|------|\n")
    report.append(f"| 主题数 | {len(topics)} |\n")
    report.append(f"| 原始资料 | {sum(len(list(d.glob('raw/*.md'))) for d in topics)} 篇 |\n")
    report.append(f"| 清洗后 | {sum(len(list(d.glob('clean/*.md'))) for d in topics)} 篇 |\n")
    report.append(f"| 合并语料 | {len(merged_mds)} 个文件, {sum(f.stat().st_size for f in merged_mds)/1024:.0f} KB |\n\n")
    
    report.append("---\n\n## 十大主题\n\n")
    
    total_raw = 0
    total_clean = 0
    
    for topic_dir in topics:
        name = topic_dir.name.replace("-", " ").replace("_", " ").strip()
        raw_files = list(topic_dir.glob("raw/*.md"))
        clean_files = list(topic_dir.glob("clean/*.md"))
        total_raw += len(raw_files)
        total_clean += len(clean_files)
        
        # 找对应的 merged file
        merged_size = 0
        for mm in merged_mds:
            if mm.stem.replace("_", " ").replace("-", " ") == name.replace(" ", ""):
                merged_size = mm.stat().st_size
                break
        
        report.append(f"### {name}\n\n")
        report.append(f"| 项目 | 数值 |\n|------|------|\n")
        report.append(f"| 原始资料 | {len(raw_files)} 篇 |\n")
        report.append(f"| 清洗后 | {len(clean_files)} 篇 |\n")
        if merged_size:
            report.append(f"| 合并大小 | {merged_size/1024:.0f} KB |\n")
        
        # 列出来源
        sources_json = topic_dir / "raw" / "sources.json"
        if sources_json.exists():
            try:
                sources = json.loads(sources_json.read_text(encoding="utf-8"))
                report.append(f"\n**资料来源:**\n\n")
                if isinstance(sources, list):
                    for s in sources[:5]:
                        url = s.get("url", "") if isinstance(s, dict) else str(s)[:80]
                        report.append(f"- {url}\n")
                elif isinstance(sources, dict):
                    urls = sources.get("urls", sources.get("sources", []))
                    for u in list(urls)[:5]:
                        report.append(f"- {u}\n")
            except:
                pass
        
        # 列出 clean 文件
        report.append(f"\n**清洗后文件:**\n\n")
        for cf in clean_files[:8]:
            report.append(f"- {cf.name} ({format_size(cf.stat().st_size)})\n")
        if len(clean_files) > 8:
            report.append(f"- ... 还有 {len(clean_files)-8} 个\n")
        
        # quality
        qf = topic_dir / "clean" / "quality.json"
        if qf.exists():
            try:
                q = json.loads(qf.read_text(encoding="utf-8"))
                score = q.get("quality_score", q.get("score", "N/A"))
                report.append(f"\n*质量评分: {score}*\n")
            except:
                pass
        
        report.append("\n---\n\n")
    
    report.append(f"\n## 统计汇总\n\n")
    report.append(f"| 项目 | 数值 |\n|------|------|\n")
    report.append(f"| 主题总数 | {len(topics)} |\n")
    report.append(f"| 原始资料合计 | {total_raw} 篇 |\n")
    report.append(f"| 清洗资料合计 | {total_clean} 篇 |\n")
    
    return "".join(report)

def main():
    print("=" * 60)
    print("复制调研资料到 ACP学习/调研资料")
    print("=" * 60)
    
    # 1. 复制整个 corpus 目录结构
    print(f"\n[1/3] 复制 raw/clean 原始资料...")
    count = copy_tree(SRC, DST)
    print(f"  复制了 {count} 个文件")
    
    # 2. 生成调研报告
    print(f"\n[2/3] 生成调研报告...")
    report = generate_report()
    report_path = DST / "调研报告.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  报告已保存: {report_path.name} ({report_path.stat().st_size/1024:.0f} KB)")
    
    # 3. 树形结构清单
    print(f"\n[3/3] 生成目录结构清单...")
    tree_lines = ["# 调研资料目录结构\n", f"> 共 {count} 个文件\n\n"]
    
    def build_tree(dir_path, prefix=""):
        entries = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            size_info = f" ({entry.stat().st_size/1024:.0f} KB)" if entry.is_file() else "/"
            tree_lines.append(f"{prefix}{connector}{entry.name}{size_info}\n")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                build_tree(entry, prefix + extension)
    
    build_tree(DST)
    
    tree_path = DST / "目录结构.txt"
    tree_path.write_text("".join(tree_lines), encoding="utf-8")
    print(f"  目录结构已保存: {tree_path.name}")
    
    # 列出最终成果
    print(f"\n{'='*60}")
    print(f"调研资料已复制到: {DST}")
    print(f"{'='*60}")
    print(f"\n目录结构:")
    print("".join(tree_lines[:40]))
    print("  ...")

if __name__ == "__main__":
    main()
