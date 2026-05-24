# 测试策略

> 分层测试方案、mock 边界、验收标准  
> 工具：pytest + pytest-asyncio + pytest-mock

---

## 一、测试金字塔

```
         ╱  E2E  ╲          手动 / CI 周跑
        ╱ 集成测试 ╲          CI 每次 push
       ╱  单元测试  ╲         CI 每次 push + pre-commit
      ────────────────
      覆盖:
      单元: ~70% 代码路径
      集成: 所有 MCP Tool 的 happy path + 3个关键失败分支
      E2E: 48h workflow 全链路
```

---

## 二、分层测试定义

### 2.1 单元测试

**范围**：单个函数/类的纯逻辑，无外部依赖。

```python
# tests/unit/test_bkt.py
def test_bkt_update_correct_answer():
    params = BKTParams(p_mastery=0.5, p_learn=0.15, p_guess=0.12, p_slip=0.08)
    updated = update_bkt(params, observation=True)
    assert 0.85 <= updated.p_mastery <= 0.95  # 正确的回答提升掌握度

def test_bkt_update_wrong_answer():
    params = BKTParams(p_mastery=0.8, p_learn=0.15, p_guess=0.12, p_slip=0.08)
    updated = update_bkt(params, observation=False)
    assert updated.p_mastery < 0.8  # 错误的回答降低掌握度

# tests/unit/test_forgetting_curve.py
def test_predict_recall_after_7_days():
    curve = ForgettingCurve(lambda_param=0.05)
    recall = curve.predict_recall(days=7)
    assert 0.68 <= recall <= 0.72  # e^(-0.05*7) ≈ 0.705

# tests/unit/test_reduction_of_order.py
def test_build_teaching_path_skips_mastered():
    kg = mock_kg_with_3_concepts()
    mastery = {"c1": 0.9, "c2": 0.5, "c3": 0.1}  # c1已掌握
    path = build_teaching_path(kg, "c3", mastery, ReductionOfOrderParams(skip_threshold=0.85))
    assert len(path.snippets) == 2  # c1被跳过，只有c2和c3
    assert path.snippets[0].concept.id == "c2"  # 先从c2开始

# tests/unit/test_schemas.py
def test_concept_id_format_invalid():
    with pytest.raises(ValidationError):
        Concept(id="invalid_format", ...)  # 缺少章节信息

def test_relation_no_self_loop():
    with pytest.raises(ValidationError):
        Relation(from_id="c1", to_id="c1", ...)  # 自环禁止
```

**Mock 规则**：
- 不 mock Python 标准库
- 不 mock Pydantic 验证
- 只 mock 外部边界（DB、HTTP、文件系统、LLM API）

---

### 2.2 集成测试

**范围**：MCP Tool 的完整调用链（含真实 SQLite、mock 的 Docker/LLM）。

```python
# tests/integration/test_knowledge_mcp.py
@pytest.fixture
def db():
    """每个测试用独立的 SQLite 内存数据库"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine

@pytest.fixture
def mock_llm():
    """Mock LLM 返回预设的概念列表"""
    with patch("shared.llm_client.LLMClient.call") as mock:
        mock.return_value = json.dumps({
            "concepts": [
                {"name": "极限的ε-δ定义", "category": "definition", ...},
            ]
        })
        yield mock

@pytest.mark.asyncio
async def test_build_kg_toc_mode(db, mock_llm):
    """TOC 模式不使用 LLM → mock 不应该被调用"""
    result = await build_knowledge_graph("corpus-test", depth="toc")
    assert result.kg_id is not None
    assert result.triples_count > 0
    mock_llm.assert_not_called()  # 关键断言：toc 模式零 LLM 调用

@pytest.mark.asyncio
async def test_build_kg_full_mode(db, mock_llm):
    result = await build_knowledge_graph("corpus-test", depth="full")
    assert result.quality_report.overall in ("pass", "pass_with_warnings")
    mock_llm.assert_called()  # full 模式必须调 LLM

# tests/integration/test_tutoring_mcp.py
@pytest.mark.asyncio
async def test_full_teaching_cycle(db_session, mock_kg):
    """完整教学片断：启动 → 下一步 → 回答 → 检查点"""
    result = await start_learning_session("test_user", "test_subject", "48h_sprint")
    session_id = result.session_id
    assert result.current_action.type == "explain"
    
    # 推进
    action = await next_action(session_id)
    assert action.type in ("ask_question", "checkpoint")
    
    # 回答（正确）
    response = await respond(session_id, "正确答案")
    assert response.correctness == "correct"
    assert response.mastery_update.change > 0

@pytest.mark.asyncio
async def test_interrupt_and_resume(db_session, mock_kg):
    """打断 → 恢复 的完整流程"""
    await start_learning_session("test_user", "test_subject", "48h_sprint")
    
    interrupt_result = await interrupt("sess-test", "为什么这里不对？")
    assert interrupt_result.checkpoint_saved
    assert interrupt_result.type == "context_aware_answer"
    
    # 恢复后继续
    action = await next_action("sess-test")
    assert action is not None  # 能正常继续
```

**关键集成测试清单**（Phase 1 至少覆盖前 5 项）：

| # | 测试场景 | 验证点 |
|---|---------|--------|
| 1 | acquire_subject with mock pdf2zh | 返回正确的 corpus_id + artifacts |
| 2 | build_kg toc mode | 零 LLM 调用，生成有效 KG |
| 3 | build_kg full mode | LLM 被调用，QualityGate 运行 |
| 4 | query_knowledge (neighbors) | 返回正确的上下游概念 |
| 5 | start_session + next_action + respond 完整片断 | mastery 正确更新 |
| 6 | interrupt + resume | 断点保存和恢复正确 |
| 7 | generate_review_plan | 复习优先级排序正确 |
| 8 | digest (quiz) | 生成有效 HTML |
| 9 | BKT 更新链：10次正确 → p_mastery > 0.9 | 收敛 |

---

### 2.3 E2E 测试

**范围**：端到端 48h workflow，使用真实 Docker 容器和真实 LLM。

```
# tests/e2e/test_workflow_48h.py

场景: 用一份 10 页的简化数学 PDF 替代 400 页教材，跑完整链路。

步骤:
1. acquire_subject → corpus_id ✓
2. build_knowledge_graph(toc) → kg_id ✓, Mermaid 图非空 ✓
3. start_learning_session → 教学计划包含所有章节 ✓
4. 模拟 10 轮教学交互:
   - 每轮: next_action → respond(正确) → next_action → respond(错误) → next_action
   - 验证: mastery 在变化，无异常
5. checkpoint → 返回 self_assessment_accuracy ✓
6. generate_review_plan → 包含已学概念的复习节点 ✓
7. digest(formats=["quiz"]) → 生成有效 HTML 文件 ✓

预期耗时: ~15 分钟（含 Docker 启动和 LLM 调用）
频率: 每周手动跑一次 / CI nightly
```

---

## 三、Mock 边界定义

```
可以 Mock 的边界:
┌────────────────────────────────────────┐
│  Docker: pdf2zh, mineru, whisper       │
│  HTTP: Tavily, DuckDuckGo, Bilibili    │
│  LLM API: DeepSeek, OpenAI, Anthropic  │
│  文件系统: 测试用 temp dir              │
│  时间: freezegun 冻结 datetime.now()   │
└────────────────────────────────────────┘

绝不 Mock 的:
┌────────────────────────────────────────┐
│  Pydantic 验证逻辑                      │
│  BKT 贝叶斯更新公式                     │
│  拓扑排序 / 图遍历算法                   │
│  状态机转换规则                          │
│  SQLAlchemy ORM（用真实 SQLite 内存库）  │
└────────────────────────────────────────┘
```

---

## 四、CI 配置

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install uv && uv sync
      - run: uv run pytest tests/unit/ -v --cov=shared --cov=servers

  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install uv && uv sync --group dev
      - run: uv run pytest tests/integration/ -v -m "not slow"

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install uv && uv sync
      - run: uv run ruff check shared/ servers/
      - run: uv run mypy shared/ servers/

  e2e:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'  # 仅 nightly
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d pdf2zh whisper redis
      - run: pip install uv && uv sync
      - run: uv run pytest tests/e2e/ -v
    env:
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
```

---

## 五、验收标准（Phase 验收门）

### Phase 1 验收

```
[ ] pytest tests/unit/ 全部通过 (覆盖率 > 70%)
[ ] 集成测试清单前 5 项通过
[ ] ruff check 零错误
[ ] mypy shared/ servers/knowledge_mcp/ 零错误
[ ] docker compose up → 4 个 server /health 全绿
[ ] 一份 10 页 PDF → toc 模式 KG → Mermaid 图可渲染
```

### Phase 2 验收

```
[ ] 集成测试清单 6-9 项通过
[ ] 一份真实 PDF (≥50页) → full 模式 KG → query_knowledge 可查询邻居
[ ] 一次完整教学片断 (start → 5轮交互 → checkpoint) 无异常
```

### Phase 3-5 验收

```
[ ] E2E 48h workflow 全链路通过
[ ] digest 生成 4 种格式产物文件有效
[ ] BKT 参数收敛验证 (10次正确回答后 p_mastery > 0.9)
[ ] 复习计划包含正确的优先级排序
```

---

## 六、测试辅助工具

```python
# tests/conftest.py 中的 fixtures

@pytest.fixture
def temp_dir(tmp_path):
    """为每个测试创建独立的临时目录"""
    return tmp_path

@pytest.fixture
def mock_kg():
    """创建一个包含 10 个概念、15 条关系的小型 KG"""
    return create_mini_kg()

@pytest.fixture
def mock_learner_profile():
    """创建一个冷启动的默认画像"""
    return LearnerProfile(user_id="test_user")

@pytest.fixture
def db_session():
    """SQLite 内存数据库 session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
```
