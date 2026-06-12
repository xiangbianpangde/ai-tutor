# 接口注释清单 — M-017 存储

> 角色：DD-M-017
> 负责模块：M-017
> 上游：DD-001 IC-001/IC-002/IC-003/IC-004/IC-007
> 来源标注：[DD-001:IC-001~008] + [DD-001:EX-011/024]

---

## IC-001 启动期 DB 初始化（来自 DD-001 IC-001）

- **关联契约**：IC-001 / API-001
- **实现文件**：`src/aitutor/storage/unit_of_work.py::init_storage`
- **实现位置**：`unit_of_work.py` — 启动期一次性调用
- **关键约束**：
  - 启动 ≤ 5s
  - SQLite WAL 模式 + busy_timeout=5000
  - Chroma client ping 一次
  - File base_path 存在性检查
- **错误码**：E00103（旧库不兼容→自动迁移）/ E01701（磁盘满）/ E01704（迁移失败→回滚+备份）
- **来源标注**：[DD-001:IC-001/EX-011]

## IC-002 回合 DB 写（来自 DD-001 IC-002）

- **关联契约**：IC-002 / API-002（E00403 DB 写失败）
- **实现文件**：`src/aitutor/storage/sqlite_repo.py::SessionRepository.update_state`
- **关键约束**：
  - 单回合 ≤ 5s（P95）
  - asyncio.Lock 保护 session 写
  - SQLite WAL（EX-024）
- **错误码**：E00403 / E01703
- **来源标注**：[DD-001:IC-002/EX-024]

## IC-003 RAG 检索（来自 DD-001 IC-003）

- **关联契约**：IC-003 / API-003
- **实现文件**：`src/aitutor/storage/chroma_repo.py::query_chroma`
- **关键约束**：
  - 单次 ≤ 10s（P95）
  - ChromaDB 单写者 + asyncio 协程读
  - 损坏自动重建（EX-012）
- **错误码**：E00802 / E01702
- **来源标注**：[DD-001:IC-003/MD-017]

## IC-004 数据入库（来自 DD-001 IC-004）

- **关联契约**：IC-004 / API-004
- **实现文件**：
  - `unit_of_work.py::init_storage`（启动时路径检查）
  - `chroma_repo.py::add_chunks`（向量入库）
  - `sqlite_repo.py::DocumentRepository.create`（元数据写入）
  - `file_store.py::write_file`（PDF 落盘）
- **关键约束**：
  - 单文件 ≤ 100MB
  - 类型白名单（.pdf）
  - 路径白名单（EX-014）
- **错误码**：E01404 / E01405 / E01701
- **来源标注**：[DD-001:IC-004/EX-014]

## IC-007 长期记忆（来自 DD-001 IC-007）

- **关联契约**：IC-007 / API-007
- **实现文件**：`src/aitutor/storage/sqlite_repo.py::MemoryRepository`
- **方法映射**：
  - `save` → `MemoryRepository.save`
  - `query` → `MemoryRepository.query`
  - `evict` → `MemoryRepository.evict_oldest`
- **关键约束**：
  - 单写 ≤ 100ms
  - 单查 ≤ 200ms
  - content_hash UNIQUE（幂等 save）
- **错误码**：E00403 / E01703
- **来源标注**：[DD-001:IC-007]

## 内部 API 清单（M-017 模块内）

| 函数 | 所在文件 | 关联 IC | 错误码 |
|------|---------|---------|--------|
| `init_storage` | unit_of_work.py | IC-001 | E00103/E01701/E01704 |
| `get_session` | unit_of_work.py | - | E01703 |
| `migrate` | unit_of_work.py | IC-001 | E01704 |
| `query/insert/update/delete` | sqlite_repo.py | IC-002/007 | E00403/E01703 |
| `query_chroma` | chroma_repo.py | IC-003 | E00802/E01702 |
| `add_chunks` | chroma_repo.py | IC-004 | E01702 |
| `read_file` | file_store.py | IC-004 | E00104/E01404 |
| `write_file` | file_store.py | IC-004 | E00104/E01404/E01701 |
| `delete_file` | file_store.py | - | E00104 |
| `V1InitialMigration.up/down` | migrations/v1_initial.py | IC-001 | E01704 |

## 来源标注

[DD-001:IC-001~008] 接口契约
[DD-001:EX-011/024] DB 异常 / 并发冲突
[DD-M推断:依据=内部 API 由 MD-017 函数签名映射]
