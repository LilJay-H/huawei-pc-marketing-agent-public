> 公开评审版说明：本文涉及团队数据包或真实运行的描述属于开发验收记录。本公开仓库不分发私有数据集、原文样例或密钥；使用者须自行配置授权资料与模型。

# 接口与配置速查

本文不含真实凭证。复制 `.env.example` 为 `.env`，填写自己的模型与资料源配置。请求示例中的ID均为占位值。

## 1. 运行与配置

运行：`python server.py`，Windows也可双击 `start-team.cmd`。访问 http://127.0.0.1:8765/ 。服务仅绑定回环地址，无局域网或公网依赖；外部模型调用需互联网。

配置 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY` 以及资料模式，模型费用由对应 API 账号承担。兼容私下提供的 `.env.team`，但公开仓库不提供或分发任何团队共享密钥。

管理员如需启用ima实时测试，在自己的 `.env` 或环境变量设置：

```ini
IMA_OPENAPI_CLIENTID=<管理员账号的Client ID>
IMA_OPENAPI_APIKEY=<管理员账号的API Key>
IMA_KB_NAME=你的知识库名称
```

其它可配置项：`LOCAL_KB_PATH=knowledge-base/v7`、`DEFAULT_SOURCE_MODE=local`、`LLM_BASE_URL=https://api.deepseek.com`、`LLM_MODEL=deepseek-flash`。公开版不含资料目录，需要自行配置获授权的本地资料或 ima 来源。

## 2. 本机应用 API

请求和响应为UTF-8 JSON。POST各字段必须为字符串，请求上限20KB。当前Host/Origin限制localhost与127.0.0.1的8765端口，不要直接反向代理成公网服务。

- `GET /api/config`：场景、平台、资料模式、配置是否存在。`*_configured`不等于已成功连接服务。
- `GET /api/products`：本地重点型号名称列表，不调用ima。
- `GET /api/local-image?file=<URL编码相对路径>`：读取知识库范围内图片；检查路径、类型、大小和签名，不提供任意文件访问。
- `POST /api/connect`：`{"source_mode":"local"}`检查本地库；`{"source_mode":"ima"}`检查指定ima库。
- `POST /api/retrieve`：读取事实与图片，不调用文案模型。
- `POST /api/generate`：完整事实提取、生成、核验与最多一次修订。
- `POST /api/rewrite`：提交已有run_id和改写后的任务字段。服务端取回旧证据，不能从浏览器上传“已验证资料”。

生成/检索任务例：

```json
{
  "source_mode": "local",
  "product": "MateBook D 14",
  "version": "2024",
  "audience": "准备开学的文科大学新生",
  "scene": "开学购机",
  "platform": "小红书",
  "stage": "比较选型",
  "goal": "帮助按学习任务选型，引导咨询",
  "requirements": "不编造价格、补贴和亲测体验；保留版本条件。"
}
```

改写例：

```json
{"run_id":"<上次返回的run_id>","platform":"公众号","requirements":"面向家长解释选择理由，删除性能堆砌。"}
```

状态：needs_input（追问）、retrieved（已读取）、model_required（团队模型配置缺失）、blocked（证据/冲突阻止）、failed（调用或解析失败）、needs_review（草稿有问题）、checked_draft（未发现问题，但需人工确认）。业务失败可能以HTTP200携带status/error返回，客户端不能只看HTTP状态。

追溯字段包括run_id、mode、source_kind、started_at、trace、evidence_manifest、verification、issues；快照改写另含parent_run_id和evidence_started_at。原文与图片链接可能在完整结果中出现，勿公开转发原始响应。

## 3. ima OpenAPI

Base URL：`https://ima.qq.com/openapi/wiki/v1/`。应用直接使用Python urllib请求；本机官方Skill仅用于参考/诊断，不是运行依赖。

HTTP POST JSON。认证头：`ima-openapi-clientid`、`ima-openapi-apikey`；另有`ima-openapi-ctx: skill_version=1.1.10`。从服务器环境读取，不传给DeepSeek。

1. `search_knowledge_base`：`{"query":"你的知识库名称","cursor":"","limit":20}`。精确匹配返回的kb_name，内部使用kb_id。
2. `search_knowledge`：字段knowledge_base_id、query（当前仅型号）、cursor。命中数作诊断，当前事实依据主要来自目录读取。
3. `get_knowledge_list`：knowledge_base_id、可选folder_id、cursor、limit=50。返回knowledge_list、is_end、next_cursor。搜索空时浏览目录，不能直接判断无权限。
4. `get_media_info`：`{"media_id":"<内部媒体ID>"}`。返回url_info.url及可能存在的url_info.headers；按返回地址读取原文。

响应检查code==0，再读data；非0显示msg。当前已观察限额错误：“资料获取次数已达上限，请明天再尝试”。库ID/媒体ID仅内部使用；不要写入演示材料。

当前支持MD/TXT/CSV原文（UTF-8，每份300KB以内），以及图片链接。PDF/笔记型原文、远端鉴权图片代理与链接刷新尚未实现。

官方凭证入口：https://ima.qq.com/agent-interface 。Skill下载：https://app-dl.ima.qq.com/skills/ima-skills-1.1.10.zip 。

## 4. DeepSeek API

负责人Key统一计费；各成员本机后端直接调用，不经过负责人电脑，也不要求同一网络。

- Base URL：`https://api.deepseek.com`。
- POST：`/chat/completions`。
- Header：`Authorization: Bearer <本机私密配置读取的Key>`。
- 当前模型：`deepseek-flash`（以服务商当前可用模型为准）。
- 请求包括model、messages；官方服务另设置response_format为json_object、thinking为disabled、max_tokens=6000。
- 读取choices[0].message.content并解析JSON；空输出、截断、格式异常不作为成功成稿。
- 发送任务、规则、事实文本和图片元数据；不发送ima凭证或图片访问链接，不分析图片像素。
- 一次完整生成最多5次模型请求；多人共用账号费用与限额。

文档：https://api-docs.deepseek.com/ 。管理后台：https://platform.deepseek.com/ 。

## 5. 命令行与测试

```powershell
python -m unittest discover -s tests -v
python cli.py retrieve --task examples/freshman-xiaohongshu.json --source local --output outputs/retrieval.json
python cli.py generate --task examples/freshman-xiaohongshu.json --source local --output outputs/generated.json
python cli.py check
```

最后一个check只检查ima，团队本地模式无需执行。CLI退出码0表示读取成功或草稿未发现问题，2表示待补充/待复核，1表示调用/解析失败。完整结果留在被Git忽略的outputs/。
