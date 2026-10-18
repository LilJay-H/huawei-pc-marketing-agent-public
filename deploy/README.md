# 赛事临时 IP 部署

保留现有 OpenClaw，应用单独以 `campus-agent` 用户运行。代码放在 `/opt/campus-agent/current`，私有配置放在 `/etc/campus-agent/environment`（root 读取，600 权限），知识库单独放在 `/var/lib/campus-agent/knowledge-base/v7`。不要将密钥或私有知识库推到公开仓库。

systemd 模板限制新应用最多 384MB 内存、半个 CPU 核，并降低调度优先级。该限制不能保证原有服务完全不受共享带宽、磁盘或操作系统资源竞争影响，部署前后需比较原有服务状态。

服务器配置文件除了模型凭证，还需要：

```ini
DEFAULT_SOURCE_MODE=local
LOCAL_KB_PATH=/var/lib/campus-agent/knowledge-base/v7
APP_ASYNC_JOBS=1
APP_ALLOWED_ORIGINS=http://你的服务器IP
```

后端仍只监听 127.0.0.1:8765。Nginx 将 HTTP 80 转发给后端，并固定上游 Host；不要向公网开放 8765。复制并替换 Nginx 模板中的 `__PUBLIC_IP__`，放入独立站点配置，先执行 `nginx -t` 再加载，不覆盖已有站点。

本次按用户要求允许匿名生成、不设每日额度或访问密码。生成、资料检索和改写采用一个工作线程，任务提交即返回编号，浏览器轮询获取状态与结果；同时最多保留 8 个等待或运行的任务，超过时返回繁忙，完成后可继续提交。这是服务器容量控制，不是每日使用额度。已完成任务最多保留 20 个、30 分钟；服务器重启后任务与证据快照失效。停止浏览器等待不会取消已经提交的模型调用。

只将必要的 HTTP 80 端口开放给评委；SSH 登录限定部署来源 IP。不要更改 OpenClaw 的端口、服务、配置或系统整体防火墙默认策略。此方案是临时 IP 评测入口；域名上线另行配置 HTTPS、域名与适用的备案要求。

验收包括：外网打开页面，读取真实资料与图片，真实模型生成，导出正文，服务重启恢复，以及 OpenClaw 原有服务仍运行。匿名访问会允许访问者使用模型额度并查看返回的资料引文，应仅对获授权展示的资料启用。

撤销本项目：停止并禁用 `campus-agent.service`，移除本项目独立 Nginx 站点并测试、重新加载 Nginx；保留资料目录便于恢复。不要直接停止共用的 Nginx 或删除其它服务。
