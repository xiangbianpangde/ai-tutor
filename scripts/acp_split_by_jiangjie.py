"""降阶法拆分：将10个主题按 ## 标题拆成 200-500 行小份"""
import re
from pathlib import Path

SRC = Path(r"C:\Users\yhn\Desktop\ACP学习\各主题资料")
DST = Path(r"C:\Users\yhn\Desktop\ACP学习\降阶拆分")
DST.mkdir(parents=True, exist_ok=True)

TOTAL_SLICES = 0

def split_file(filepath):
    """把一个 md 文件按 ## 标题拆成多个小文件"""
    global TOTAL_SLICES
    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    
    # 找所有 ## 标题的位置（行号）
    h2_positions = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            h2_positions.append(i)
    
    # 如果没有 ##，尝试用 ###
    if not h2_positions:
        for i, line in enumerate(lines):
            if line.startswith("### "):
                h2_positions.append(i)
    
    # 如果还没有，整文件当一份
    if not h2_positions:
        h2_positions = [0]
    
    # 按 ## 拆分
    stem = filepath.stem
    slices = []
    
    for idx, start in enumerate(h2_positions):
        end = h2_positions[idx + 1] if idx + 1 < len(h2_positions) else len(lines)
        chunk_lines = lines[start:end]
        chunk_text = "\n".join(chunk_lines)
        
        # 取第一个 ## 标题作为文件名
        title_line = chunk_lines[0] if chunk_lines else ""
        title = title_line.replace("## ", "").replace("# ", "").strip()
        # 清理文件名非法字符
        safe_title = re.sub(r'[\\/:*?"<>|]', '', title)[:40]
        safe_title = re.sub(r'\s+', '_', safe_title.strip())
        
        n_lines = len(chunk_lines)
        
        # 如果这一块太大了（>600行），继续按 ### 拆
        if n_lines > 600:
            h3_positions = [j for j, l in enumerate(chunk_lines) if l.startswith("### ")]
            if len(h3_positions) > 1:
                for h3_idx, h3_start in enumerate(h3_positions):
                    h3_end = h3_positions[h3_idx + 1] if h3_idx + 1 < len(h3_positions) else len(chunk_lines)
                    sub_chunk = chunk_lines[h3_start:h3_end]
                    sub_title = sub_chunk[0].replace("### ", "").strip()
                    safe_sub = re.sub(r'[\\/:*?"<>|]', '', sub_title)[:30]
                    safe_sub = re.sub(r'\s+', '_', safe_sub.strip())
                    fname = f"{idx+1:02d}_{safe_sub}.md" if safe_sub else f"{idx+1:02d}_{safe_title[:20]}.md"
                    slices.append((fname, sub_chunk))
                    TOTAL_SLICES += 1
                continue
        
        fname = f"{idx+1:02d}_{safe_title[:25]}.md" if safe_title else f"{idx+1:02d}.md"
        slices.append((fname, chunk_lines))
        TOTAL_SLICES += 1
    
    # 写文件
    topic_dir = DST / stem
    topic_dir.mkdir(exist_ok=True)
    
    # 生成该主题的索引
    index_lines = [
        f"# {stem}\n",
        f"> 源文件: {filepath.name} ({filepath.stat().st_size/1024:.0f} KB, {len(lines)} 行)\n",
        f"> 拆分后: {len(slices)} 份\n",
        f"> 建议学习顺序: 按编号顺序阅读\n\n",
        "---\n\n## 目录\n\n",
    ]
    
    for i, (fname, chunk_lines) in enumerate(slices, 1):
        chunk_text = "\n".join(chunk_lines)
        # 取第一行作为描述
        desc = chunk_lines[0] if chunk_lines else "(无标题)"
        index_lines.append(f"{i:3d}. [{desc[2:].strip() if desc.startswith('#') else desc.strip()}]({fname})  — {len(chunk_lines)} 行\n")
        
        chunk_path = topic_dir / fname
        chunk_path.write_text(chunk_text, encoding="utf-8")
    
    # 写索引文件
    index_path = topic_dir / "00_索引.md"
    index_path.write_text("".join(index_lines), encoding="utf-8")
    
    print(f"  {stem}: {len(slices)} 份 → {topic_dir}")
    return len(slices)

def generate_master_index():
    """生成总索引：建议学习路线"""
    topics = sorted(SRC.glob("*.md"))
    
    # 建议学习顺序（从基础到应用）
    order = [
        ("damoxingjichulilun", 1, "大模型基础"),
        ("aliyunacpdamoxingyingyongrenzheng", 2, "ACP考试大纲"),
        ("tishicigongcheng", 3, "提示词工程"),
        ("ragjiansuozengqiangshengcheng", 4, "RAG检索增强"),
        ("damoxingweidiao", 5, "模型微调"),
        ("ai_agent_zhinengti", 6, "AI Agent"),
        ("aliyunbailiandamoxingpingtai", 7, "百炼平台"),
        ("aliyuntongyiqianwen", 8, "Qwen API"),
        ("damoxingyingyongkaifa", 9, "LangChain"),
        ("damoxingbushu", 10, "部署优化"),
    ]
    
    index = []
    index.append("# ACP大模型应用 · 降阶学习路线\n\n")
    index.append("> 按「基础→核心→实战」的顺序排列，每份可 15-30 分钟读完\n\n")
    index.append("---\n\n## 推荐学习顺序\n\n")
    index.append("| 顺序 | 主题 | 难度 | 预计时间 | 前置要求 |\n")
    index.append("|------|------|------|---------|---------|\n")
    
    for i, (prefix, order_num, display_name) in enumerate(order, 1):
        # 难度估算
        if i <= 2: diff = "⭐ 基础"
        elif i <= 4: diff = "⭐⭐ 核心"
        elif i <= 6: diff = "⭐⭐⭐ 进阶"
        else: diff = "⭐⭐⭐⭐ 实战"
        
        # 时间估算
        time = f"{10 + i * 5}-{15 + i * 5} min"
        
        # 前置
        pre = "-" if i == 1 else f"第 {i-1} 章"
        
        # 找对应的拆分目录
        for topic_dir in sorted(DST.iterdir()):
            if topic_dir.is_dir() and topic_dir.name.startswith(prefix):
                index_line = f"| {order_num} | [{display_name}]({topic_dir.name}/00_索引.md) | {diff} | {time} | {pre} |\n"
                index.append(index_line)
                break
    
    index.append("\n---\n\n## 学习建议\n\n")
    index.append("1. **按顺序学**：每章依赖前一章\n")
    index.append("2. **每份 15-30 分钟**：建议一次读 1-2 份\n")
    index.append("3. **读完做测验**：用 `复习产物/quiz-*.html` 自测\n")
    index.append("4. **看不懂跳下一份**：回头再看，不要卡住\n")
    index.append("5. **结合精讲教程**：配合 `零基础精讲教程.md` 理解核心概念\n")
    
    (DST / "README.md").write_text("".join(index), encoding="utf-8")
    print(f"\n总索引: {DST / 'README.md'}")

def main():
    print("=" * 60)
    print("降阶法拆分 — 54,778 行 → 小份")
    print("=" * 60)
    
    files = sorted(SRC.glob("*.md"))
    print(f"\n共 {len(files)} 个主题文件\n")
    
    total = 0
    for f in files:
        n = split_file(f)
        total += n
    
    generate_master_index()
    
    print(f"\n{'='*60}")
    print(f"拆分完成: {total} 份小文件")
    print(f"输出目录: {DST}")
    print(f"{'='*60}")
    
    # 统计
    print(f"\n每份行数分布:")
    sizes = []
    for d in DST.iterdir():
        if d.is_dir():
            for f in d.glob("*.md"):
                if f.name != "00_索引.md":
                    lines = len(f.read_text(encoding="utf-8").splitlines())
                    sizes.append(lines)
    if sizes:
        avg = sum(sizes) / len(sizes)
        print(f"  平均: {avg:.0f} 行/份")
        print(f"  最小: {min(sizes)} 行")
        print(f"  最大: {max(sizes)} 行")

if __name__ == "__main__":
    main()
