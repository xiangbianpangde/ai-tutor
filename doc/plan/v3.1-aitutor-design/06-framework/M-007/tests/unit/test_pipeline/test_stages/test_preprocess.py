"""test_preprocess - PreprocessStage 单元测试

> 对应模块: M-007
> 来源标注: [DD-001:MD-M-007 子模块 sm007-preprocess]
[文件职责]  PreprocessStage 测试
[测试策略]  单元 / 4 用例（核心 2 + 边界 1 + 异常 1）/ Mock[jieba]

[测试场景清单]
  - 测试场景1: 正常 query 预处理
    断言: 返回 QueryFeatures 含 keywords/intent
    Mock: jieba.cut
  - 测试场景2: 长度超 [1, 2000] 抛 ValidationError
    断言: 抛 ValidationError
    Mock: 无
  - 测试场景3: 空 query 抛 ValidationError
    断言: 抛 ValidationError
    Mock: 无
  - 测试场景4: 关键词提取（TF-IDF）空列表
    断言: extract_keywords 返回 []
    Mock: TF-IDF 模型

[来源标注]  [DD-001:MD-M-007 子模块 sm007-preprocess]
"""
import pytest

# [DD-001:MD-M-007 sm007-preprocess] 阶段 1 测试
# [DD-001:IC-002 入参 query 长度 [1, 2000]] 边界
