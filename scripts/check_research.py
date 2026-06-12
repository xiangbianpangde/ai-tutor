"""Check if research-tool is installed."""
import sys
sys.path.insert(0, r"C:\Users\yhn\Desktop\ai-tutor")

try:
    from research_tool import create_pipeline, PipelineConfig
    print("research-tool OK")
    # Show version
    if hasattr(create_pipeline, "__module__"):
        print(f"  module: {create_pipeline.__module__}")
except ImportError as e:
    print(f"research-tool MISSING: {e}")
    print("Run: uv sync --extra research --extra dev")
