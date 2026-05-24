"""LLM provider 实现合集。

每个 provider 实现 shared.llm_client.LLMProvider Protocol，
通过 shared.plugins.PluginRegistry 注册（category='llm'）。
"""
