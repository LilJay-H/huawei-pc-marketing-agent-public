# 公开版知识库配置

公开仓库不包含团队私有的 v7 原文、图片、ZIP 或数据清单。请勿把这些资料或自己的 API Key 提交到公开仓库。

## 本地资料模式

在 `.env` 中配置 `DEFAULT_SOURCE_MODE=local` 和 `LOCAL_KB_PATH=你的授权资料目录`。目录格式由 `local_kb.py` 定义：资料根目录下包含 `P1-产品参数库/<分类>/<型号>/`，产品文档为 Markdown，图片及索引放在对应型号目录。具体格式与合成测试夹具见 `tests/test_local_kb.py`。

若已获授权使用团队数据集，可在本机单独放置并配置路径；数据不随本公开仓库分发。代码保留私有 ZIP 校验适配能力，但公开仓库不提供该 ZIP 或清单。

## ima 模式

按 `.env.example` 配置自己获授权的 ima 共享知识库与 OpenAPI 凭证，设置 `DEFAULT_SOURCE_MODE=ima`。接口说明见 `docs/INTERFACES.md`。本轮公开版没有进行新的实时 ima 验收。

完整写作还需要配置 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`。没有资料或模型时，系统应明确提示缺失条件，不生成假正文。
