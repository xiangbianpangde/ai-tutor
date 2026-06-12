"""tests.unit.test_build.test_nuitka - NuitkaBuilder 测试。

> 对应模块: M-015 / nuitka.py
> 测试策略: 单测 / 3 用例（核心 1 + 平台差异 1 + 异常 1）
> 来源标注: [DD-001:MD-M015 子模块 sm015-nuitka]

[文件路径] tests/unit/test_build/test_nuitka.py
[文件职责] 测试 NuitkaBuilder 三平台参数生成 + 工具链检测
[所属模块] M-015（测试）
[作者] DD-M-015-20260602

[测试场景清单]

  [测试场景1: test_nuitka_builder_linux_args]
    断言: Linux 平台 CLI 参数含 --static-libpython=no 和 --onefile/--onedir
    Mock: 无（纯参数生成）
    来源: [DD-M推断:依据=Nuitka Linux 编译标志]

  [测试场景2: test_nuitka_builder_windows_args]
    断言: Windows 平台 CLI 参数含 --mingw64
    Mock: 无
    来源: [DD-M推断:依据=Nuitka Windows 编译标志]

  [测试场景3: test_nuitka_builder_toolchain_unavailable_raises]
    断言: 未安装 nuitka 时抛 BuildError("toolchain_incompatible")，错误码 E01502
    Mock: shutil.which 返回 None
    来源: [DD-001:IC-005 E01502]
"""

# import pytest
# from unittest.mock import patch
#
# from aitutor.build.nuitka import NuitkaBuilder
# from aitutor.shared.exceptions import BuildError
#
#
# def test_nuitka_builder_linux_args():
#     """测试场景1: Linux 参数含 --static-libpython=no。"""
#     ...
#
#
# def test_nuitka_builder_windows_args():
#     """测试场景2: Windows 参数含 --mingw64。"""
#     ...
#
#
# def test_nuitka_builder_toolchain_unavailable_raises():
#     """测试场景3: 工具链不可用抛 E01502。"""
#     with patch("shutil.which", return_value=None):
#         with pytest.raises(BuildError, match="toolchain_incompatible"):
#             ...
