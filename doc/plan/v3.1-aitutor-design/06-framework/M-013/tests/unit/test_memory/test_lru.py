"""test_lru - LRUEviction 淘汰策略测试

[文件路径] tests/unit/test_memory/test_lru.py
[所属模块] M-013
[测试目标] 验证 LRU 候选选择 + 触发条件 + 批量淘汰
[Mock 策略] 内存 SQLite + LRUEviction 实例
[来源标注] [DD-001:MD-013 sm013-evict] + [DD-001:IC-007 E01302]
"""
from __future__ import annotations

# [测试场景1: 候选选择] [断言: 按 last_access 升序选最旧 N 条] [Mock: 内存 SQLite]
def test_select_victims_oldest_first() -> None:
    """测试场景: 100 条记忆 × 0.1 = 10 条最旧被选中。"""
    ...

# [测试场景2: 触发条件] [断言: current<max 不触发] [Mock: 无]
def test_should_trigger_false() -> None:
    """测试场景: current < max_capacity 不触发。"""
    ...

# [测试场景3: 触发条件] [断言: current>=max 触发] [Mock: 无]
def test_should_trigger_true() -> None:
    """测试场景: current == max_capacity 触发。"""
    ...

# [测试场景4: 完整 run] [断言: 返回淘汰数 = 容量 × 0.1] [Mock: 内存 SQLite]
def test_run_evicts_oldest_10_percent() -> None:
    """测试场景: run() 淘汰最旧 10%。"""
    ...

# [测试场景5: 异常路径] [断言: 删除失败抛 StorageError] [Mock: repository 抛错]
def test_run_raises_storage_error() -> None:
    """测试场景: 模拟删除失败触发 E01302 路径。"""
    ...
