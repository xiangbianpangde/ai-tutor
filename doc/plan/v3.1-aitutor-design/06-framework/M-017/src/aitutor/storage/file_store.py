"""storage.file_store - M-017 文件存储

> 对应模块: M-017 存储
> 关联接口: IC-004（数据入库：原文存储）/ IC-005（打包构建：artifact 存储）
> 关联选型: TS-001 Python 标准库 pathlib
> 关联设计: MD-AITutor-V3.1#m-017 类设计 FileStore
> 来源标注: [DD-001:MD-017] + [DD-M推断:依据=Facade 模式]
"""

# [文件职责] 文件存储 Facade（path 白名单 + 原子写 + 大文件分块）
# [所属模块] M-017
# [关联设计规范] MD-AITutor-V3.1#m-017 FileStore
# [功能描述]
#   功能1: 限制在 base_path 内的安全路径操作（防 CE-005 路径穿越）
#   功能2: 原子写（先写 .tmp，再 rename 覆盖）
#   功能3: 大文件分块读（>50MB）
#   功能4: 磁盘满检测（OSError 转 StorageError E01701）
# [输入输出]
#   输入: 相对路径 / bytes
#   输出: bytes / None
# [依赖关系]
#   依赖文件: shared/exceptions.py
#   被依赖文件: ingest/ingester.py（M-014）/ build/verifier.py（M-015）
# [注意事项]
#   注意1: 路径必须经过白名单校验，禁止绝对路径（CS-AITutor-V3.1 §8 安全规范）
#   注意2: 原子写防止半写入文件被读取
#   注意3: 同一文件并发写通过文件锁（fcntl）串行化
#   注意4: 删除/写入失败必须记录到 audit_log
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [作者] DD-M-017-20260602
# [来源标注] [DD-001:MD-017]

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import AsyncIterator, Optional

from aitutor.shared.exceptions import StorageError


# 合法相对路径正则：禁止 ../ / 绝对路径
_SAFE_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_\-./]+$")


# ============================================================
# 类：FileStore
# ============================================================


class FileStore:
    """文件存储 Facade。

    [类名] FileStore
    [职责] 统一封装文件读/写/删；提供安全路径校验 + 原子写
    [关联设计规范] MD-AITutor-V3.1#m-017 FileStore
    [属性]
      属性1: base_path Path 必填 根目录（默认 ~/.<app>/）
      属性2: _max_file_size int 内部 默认 100MB 单文件上限
      属性3: _chunk_size int 内部 默认 8MB 分块读粒度
    [方法列表]
      方法1: read(path, chunked) - 读取文件
      方法2: write(path, data) - 原子写入
      方法3: delete(path) - 删除文件
      方法4: exists(path) - 判断存在
      方法5: list(prefix) - 列出子路径
    [异常处理]
      异常1: StorageError - 磁盘满（E01701）
      异常2: ValueError - 路径非法（CE-005）
      异常3: FileNotFoundError - 读取不存在
    [并发安全] 是（文件锁）
    [幂等性] write 幂等（覆盖）；delete 幂等
    [性能约束] 100MB 写 ≤2s（P95）；50MB 读 ≤1s（P95）
    [来源标注] [DD-001:MD-017]
    """

    def __init__(
        self,
        base_path: Path,
        max_file_size: int = 100 * 1024 * 1024,
        chunk_size: int = 8 * 1024 * 1024,
    ) -> None:
        """初始化 FileStore。

        [函数名] __init__
        [职责] 创建根目录（如不存在）+ 初始化阈值
        [参数说明]
          参数1: base_path Path 必填 根目录
          参数2: max_file_size int 可选 默认 100MB
          参数3: chunk_size int 可选 默认 8MB
        [返回值]
          类型: None
        [错误码]
          错误码1: E01701 含义: 磁盘满 触发: 创建目录失败
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def read(
        self,
        path: str,
        chunked: bool = False,
    ) -> bytes:
        """读取文件。

        [函数名] read
        [职责] 校验路径 → 读取全部或分块流
        [参数说明]
          参数1: path str 必填 相对路径
          参数2: chunked bool 可选 默认 False 是否分块流式读
        [返回值]
          类型: bytes
          描述: 文件内容（chunked=False 时完整返回；否则用 stream_read）
        [错误码]
          错误码1: ValueError 含义: 路径非法 触发: 越界或绝对路径
          错误码2: FileNotFoundError 含义: 文件不存在
        [并发安全] 是
        [幂等性] 是
        [性能约束] 50MB ≤1s（P95）
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def write(self, path: str, data: bytes) -> None:
        """原子写入文件。

        [函数名] write
        [职责] 校验路径 → 写临时文件 → rename 覆盖
        [参数说明]
          参数1: path str 必填 相对路径
          参数2: data bytes 必填 文件内容
        [返回值]
          类型: None
        [错误码]
          错误码1: E01701 含义: 磁盘满 触发: 写临时文件失败
          错误码2: ValueError 含义: 路径非法
        [并发安全] 是（文件锁）
        [幂等性] 是（覆盖）
        [性能约束] 100MB ≤2s（P95）
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def delete(self, path: str) -> None:
        """删除文件。

        [函数名] delete
        [职责] 校验路径 → 删除
        [参数说明]
          参数1: path str 必填 相对路径
        [返回值]
          类型: None
        [错误码]
          错误码1: ValueError 含义: 路径非法
          错误码2: FileNotFoundError 含义: 文件不存在
        [并发安全] 是
        [幂等性] 是
        [性能约束] ≤50ms
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def exists(self, path: str) -> bool:
        """判断文件是否存在。

        [函数名] exists
        [职责] 校验路径 → os.path.exists
        [参数说明]
          参数1: path str 必填
        [返回值]
          类型: bool
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def list(self, prefix: str = "") -> list[str]:
        """列出子路径。

        [函数名] list
        [职责] 列出 base_path 下的所有相对路径
        [参数说明]
          参数1: prefix str 可选 默认 "" 前缀过滤
        [返回值]
          类型: List[str]
          描述: 相对路径列表
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def stream_read(self, path: str) -> AsyncIterator[bytes]:
        """分块流式读取。

        [函数名] stream_read
        [职责] 大文件按 chunk_size 分块 yield
        [参数说明]
          参数1: path str 必填
        [返回值]
          类型: AsyncIterator[bytes]
        [来源标注] [DD-001:MD-017]
        """
        ...

    def _validate_path(self, path: str) -> Path:
        """校验路径安全（内部方法）。

        [函数名] _validate_path
        [职责] 检查相对路径安全 + 解析绝对路径
        [参数说明]
          参数1: path str 必填
        [返回值]
          类型: Path
          描述: 解析后的绝对路径
        [错误码]
          错误码1: ValueError 含义: 路径非法 触发: 越界或绝对路径
        [来源标注] [DD-M推断:依据=CS-AITutor-V3.1 §8 安全规范]
        """
        ...
