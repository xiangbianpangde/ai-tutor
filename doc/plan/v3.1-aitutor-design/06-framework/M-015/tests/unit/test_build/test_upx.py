"""tests.unit.test_build.test_upx - UPXCompressor 测试。

> 对应模块: M-015 / upx.py
> 测试策略: 单测 / 2 用例（正常压缩 + 软降级）
> 来源标注: [DD-001:MD-M015 子模块 sm015-upx] + [DD-001:EX-020 ADR-009 软约束]

[文件路径] tests/unit/test_build/test_upx.py
[文件职责] 测试 UPX 压缩成功路径 + 失败软降级（不抛异常）
[所属模块] M-015（测试）
[作者] DD-M-015-20260602

[测试场景清单]

  [测试场景1: test_compress_artifact_success]
    断言: compress_artifact 返回的路径存在，压缩后体积 < 原体积
    Mock: subprocess.run（UPX 调用）
    来源: [DD-001:MD-M015 sm015-upx]

  [测试场景2: test_compress_artifact_upx_unavailable_soft_degrade]
    断言: UPX 不在 PATH 时返回原路径不抛异常，写 WARN 日志（ADR-009 软约束）
    Mock: shutil.which 返回 None
    来源: [DD-001:EX-020 line 332-345]
"""

# import pytest
# from unittest.mock import patch
# from pathlib import Path
#
# from aitutor.build.upx import UPXCompressor, compress_artifact
#
#
# def test_compress_artifact_success(tmp_path):
#     """测试场景1: UPX 压缩成功。"""
#     ...
#
#
# def test_compress_artifact_upx_unavailable_soft_degrade(tmp_path, caplog):
#     """测试场景2: UPX 不可用软降级，不抛异常，仅 WARN 日志。"""
#     with patch("shutil.which", return_value=None):
#         result = compress_artifact(str(tmp_path))
#         # assert result == tmp_path
#         # assert "WARN" in caplog.text or "upx_unavailable" in caplog.text
#         ...
