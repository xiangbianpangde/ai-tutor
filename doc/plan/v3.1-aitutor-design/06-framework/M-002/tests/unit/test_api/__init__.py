"""M-002 API 网关 + WS - 测试套件初始化。

[文件路径] tests/unit/test_api/__init__.py
[文件职责] M-002 测试目录初始化，公共 fixture 入口。
[所属模块] M-002 API 网关 + WS
[关联设计规范] FS-M-002 / MD-M-002 测试策略
[功能描述]
  功能1: 提供共享 fixture（mock_token, mock_user_context, test_app）
  功能2: 导出测试公共工具（auth_header_builder, ws_mock_client）
[输入输出]
  输入: 无
  输出: 暴露公共测试符号
[依赖关系]
  依赖文件: tests/conftest.py
  被依赖文件: tests/unit/test_api/test_*.py
[注意事项]
  注意1: 严禁在 __init__.py 中写测试用例
  注意2: 共享 fixture 避免重复
[代码风格] 遵循 CS-NNN
[创建日期] 2026-06-02
[作者] DD-M-002-20260602
[来源标注] [DD-001:FS-M-002] + [DD-001:MD-M-002 测试策略]
"""

# 仅注释占位
# import pytest
# from fastapi.testclient import TestClient
# from aitutor.api.auth import UserContext
#
# @pytest.fixture
# def mock_user_context() -> UserContext:
#     """构造测试用 UserContext."""
#     pass
#
# @pytest.fixture
# def mock_token() -> str:
#     """构造测试用 Bearer Token."""
#     pass
