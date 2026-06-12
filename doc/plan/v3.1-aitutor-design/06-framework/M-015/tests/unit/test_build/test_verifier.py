"""tests.unit.test_build.test_verifier - ArtifactVerifier 测试。

> 对应模块: M-015 / verifier.py
> 测试策略: 单测 / 3 用例（sha256 计算 + 体积门禁 + 不匹配异常）
> 来源标注: [DD-001:MD-M015 子模块 sm015-verify] + [DD-001:IC-005 E01501/E01503]

[文件路径] tests/unit/test_build/test_verifier.py
[文件职责] 测试 sha256 流式计算 + 体积门禁 + sha256 不匹配抛异常
[所属模块] M-015（测试）
[作者] DD-M-015-20260602

[测试场景清单]

  [测试场景1: test_verify_artifact_sha256_calculation]
    断言: sha256 输出为 64hex 字符串，与 hashlib 直接计算结果一致
    Mock: 无（真实文件）
    来源: [DD-001:IC-005 出参 sha256]

  [测试场景2: test_verify_artifact_size_warn_only]
    断言: CLI 体积 >50MB 时 result.is_warn_size()=True，passed 不报错
    Mock: _compute_size 返回 60*1024*1024
    来源: [DD-001:IC-005 E01501 / ADR-009]

  [测试场景3: test_verify_artifact_sha256_mismatch_raises]
    断言: 提供 expected_sha256 但计算结果不一致时抛 BuildError("sha256_mismatch")
    Mock: 无
    来源: [DD-001:IC-005 E01503]
"""

# import pytest
# import hashlib
# from pathlib import Path
#
# from aitutor.build.verifier import ArtifactVerifier, verify_artifact, VerifyResult
# from aitutor.shared.exceptions import BuildError
#
#
# def test_verify_artifact_sha256_calculation(tmp_path):
#     """测试场景1: sha256 正确性（与 hashlib 直接调用一致）。"""
#     file = tmp_path / "test.bin"
#     file.write_bytes(b"hello world")
#     expected = hashlib.sha256(b"hello world").hexdigest()
#     # result = verify_artifact(str(file), format="cli")
#     # assert result.sha256 == expected
#     ...
#
#
# def test_verify_artifact_size_warn_only(tmp_path):
#     """测试场景2: 体积超目标仅 WARN，passed 字段反映软约束。"""
#     ...
#
#
# def test_verify_artifact_sha256_mismatch_raises(tmp_path):
#     """测试场景3: sha256 不匹配抛 E01503。"""
#     with pytest.raises(BuildError, match="sha256_mismatch"):
#         ...
