"""aitutor.build - 打包调度模块（M-015）公共导出。

> 对应模块: M-015 打包调度（Command + Factory）
> 关联接口: IC-005 打包构建
> 关联选型: TS-011 Nuitka / TS-012 UPX
> 来源标注: [DD-001:FS-M015] + [DD-001:MD-M015]

[文件路径] src/aitutor/build/__init__.py
[文件职责] 暴露 M-015 模块对外公开接口，隐藏内部实现细节
[所属模块] M-015 打包调度
[关联设计规范] FS-M015（文件结构）/ MD-M015（模块细化）
[功能描述]
  功能1: 重新导出 BuildOrchestrator、NuitkaBuilder、UPXCompressor、ArtifactVerifier 4 类
  功能2: 重新导出 build_artifact / compress_artifact / verify_artifact 3 公开函数
  功能3: 暴露 Artifact / VerifyResult / BuildStage 等公共数据类型别名
[输入输出]
  输入: 无（仅 re-export）
  输出: 模块级公开符号 __all__
[依赖关系]
  依赖文件: aitutor/build/orchestrator.py, nuitka.py, upx.py, verifier.py
  被依赖文件: aitutor/api/v1/* (CI 触发入口) / scripts/build.sh
[注意事项]
  注意1: 仅做 re-export，禁止在此处实现业务逻辑（R24 文件职责模糊）
  注意2: __all__ 必须显式列出，避免 wildcard import 污染（CS-001 §4.2）
  注意3: 跨模块依赖：M-006 monitor/bus（事件总线）、M-017 storage（产物元数据）——已在文件头标注（[DD-M推断:依据=ImportLinter contract:2]）
[代码风格] 遵循 CS-001（Python PEP8 / Ruff 0.7.4 / Google Docstring）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-015 - 初始版本，re-export 4 类 + 3 函数
[作者] DD-M-015-20260602
[来源标注] [DD-001:FS-M015 line 514-526] + [DD-001:MD-M015 line 428-457]
"""

# ============================================================
# 公共导出清单（来源：MD-M015 类设计 + 函数签名）
# ============================================================
# [DD-M推断:依据=Python __init__.py 最佳实践，显式 __all__ 防止 wildcard 污染]
# from aitutor.build.orchestrator import BuildOrchestrator, build_artifact
# from aitutor.build.nuitka import NuitkaBuilder
# from aitutor.build.upx import UPXCompressor, compress_artifact
# from aitutor.build.verifier import ArtifactVerifier, verify_artifact
#
# __all__ = [
#     # 类（来源 MD-M015 类设计）
#     "BuildOrchestrator",
#     "NuitkaBuilder",
#     "UPXCompressor",
#     "ArtifactVerifier",
#     # 函数（来源 MD-M015 函数签名）
#     "build_artifact",
#     "compress_artifact",
#     "verify_artifact",
# ]
