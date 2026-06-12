# FDR-M-002-AITutor-V3.1-20260602 — M-002 API 网关 + WS 框架决策记录

> 负责模块: M-002 API 网关 + WS
> 决策数量: 4 项
> 来源标注: [DD-001:MD-M-002] + [DD-001:IC-001/002/004/008] + [DD-M推断]

---

## FDR-M002-001 v1 路由版本目录隔离

[决策编号] FDR-M002-001
[决策标题] v1 路由通过子目录 v1/ 隔离，便于未来 v2 升级
[决策状态] 已接受
[决策内容] 所有 v1 路由文件置于 `src/aitutor/api/v1/` 子目录，APIRouter 统一前缀 `/api/v1`
[决策理由]
- 未来 v2 升级时可独立 `v2/` 子目录，不影响 v1 兼容（[DD-001:FS-M-002 目录层级 3 层]）
- OpenAPI tag 自动按子目录分组（[调研报告:REDOC-30~53 openapi-tags]）
- 4 工具链（Import Linter）可通过 `forbidden` contract 强制 v1 内部跨文件不互引
[拒绝的替代方案]
- 单层 `api/` 目录 + `session_v1.py` 后缀命名 → 拒绝理由：违反 [DD-001:CS-NNN 命名规则]，未来 v2 时命名爆炸
- 模块化（每个 IC 一个子包 `turns/`、`sessions/`）→ 拒绝理由：过度拆分，与 FS-M-002 不一致
[影响范围] M-002 全部路由文件（v1/session.py, v1/turn.py, v1/ingest.py, v1/health.py, v1/ws.py）
[相关FDR] FDR-M002-002
[来源标注] [DD-001:FS-M-002] + [DD-M推断:依据=API 版本管理最佳实践]

---

## FDR-M002-002 鉴权与限流解耦

[决策编号] FDR-M002-002
[决策标题] AuthDependency 与 RateLimiter 分离为独立文件
[决策状态] 已接受
[决策内容] `auth.py` 负责 Token 校验 + UserContext 构造；`rate_limit.py` 负责限流策略；两者通过 `deps.py` Depends 注入解耦
[决策理由]
- 关注点分离：鉴权无状态 + 可缓存，限流带状态 + 需锁
- 单元测试可独立 mock：[CS-NNN 测试规范]
- 多租户扩展时仅需修改 `rate_limit.py`，不影响鉴权
- Import Linter `forbidden` contract 可分别约束两个文件
[拒绝的替代方案]
- 合并为 `gateway.py` 单文件 → 拒绝理由：违反 R24 文件职责模糊
- 限流作为 `auth.py` 子模块 → 拒绝理由：限流与鉴权职责无关，合并导致循环依赖风险
[影响范围] src/aitutor/api/auth.py, src/aitutor/api/rate_limit.py, src/aitutor/api/deps.py
[相关FDR] FDR-M002-001
[来源标注] [DD-001:MD-M-002] + [DD-M推断:依据=关注点分离原则 + 单一职责]

---

## FDR-M002-003 WS 软硬限流双阈值

[决策编号] FDR-M002-003
[决策标题] WS 连接数采用 80% 软拒绝 + 100% 硬拒绝双阈值
[决策状态] 已接受
[决策内容] WSConnectionManager 维护 `soft_limit=800` 与 `max_connections=1000` 两个阈值；800~1000 区间软拒绝（返回 E00202 + 提示客户端降级轮询），>1000 硬拒绝
[决策理由]
- 1000 个断连同时重连将导致事件总线堵塞（[DD-001:DD洞察-004 雷鸣群 herd effect]）
- 软拒绝给予客户端 30s 退避窗口（base=1s, max=30s, jitter±30%）
- 硬拒绝保留最后 200 连接缓冲，应对突发流量
- Prometheus 监控可在 80% 触发 WARN 告警（[AR:BR-038]）
[拒绝的替代方案]
- 单一 1000 硬阈值 → 拒绝理由：无退避窗口，雷鸣群场景必堵塞
- 动态阈值（按 CPU/内存负载）→ 拒绝理由：实现复杂度过高，V3.1 不必要（V4.0 可演进）
[影响范围] src/aitutor/api/v1/ws.py（WSConnectionManager 类）
[相关FDR] FDR-M002-004
[来源标注] [DD-001:IC-008 max=1000] + [DD-001:EX-002] + [DD-001:DD洞察-004]

---

## FDR-M002-004 测试文件按子能力分文件

[决策编号] FDR-M002-004
[决策标题] 测试文件按子能力（auth / rate_limit / ws）分文件，E2E 单独成文
[决策状态] 已接受
[决策内容] 单元测试 3 个文件（test_auth / test_rate_limit / test_ws），集成测试 1 个文件（test_api_e2e）
[决策理由]
- 16 用例分散到 3 个单元测试文件便于维护（每文件 5~7 用例）
- E2E 单独成文便于 CI 区分快速/完整跑（[DD-001:MD-M-002 测试策略 16 用例 = 核心 6 + 边界 6 + 异常 4]）
- 与 FS-M-002 镜像结构一致（[CS-NNN 测试镜像规范]）
[拒绝的替代方案]
- 单文件 test_api.py（16 用例）→ 拒绝理由：文件过大（违反 R24，单文件 ≤ 20 函数），定位失败慢
- 按 IC 拆分（test_session_e2e.py, test_turn_e2e.py）→ 拒绝理由：与 FS-M-002 文件结构不镜像
[影响范围] tests/unit/test_api/, tests/integration/
[相关FDR] FDR-M002-001
[来源标注] [DD-001:MD-M-002 测试策略] + [DD-M推断:依据=pytest 最佳实践]

---

## FDR 覆盖率

- 决策类型: 文件组织 / 职责分离 / 限流策略 / 测试组织
- 4/4 = 100% 覆盖（M-002 全部重大框架决策）
- 状态: 全部「已接受」

来源标注: [DD-001:MD-M-002] + [DD-001:IC-001/002/004/008] + [DD-001:DD洞察-004] + [DD-M推断]
