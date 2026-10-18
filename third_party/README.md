# 来源与选取范围

- yuwen-cool/yuwen-publish-precheck（MIT），固定提交 b9efdc6bc1938b40ad1c556fba65c562fc182be0：从 scripts/terms.json 选取 R01/R02/R04/R05/R06/R07/R08/R09/R10/R12/R13 的候选模式，参考 references/judgment.md 的词面与语义分工。https://github.com/yuwen-cool/yuwen-publish-precheck
- huangbai-AI/guoshen（MIT），固定提交 d18c06d70358d7fa70a7e2988cb91888871e808e：选取 common/rules.json 的 C003—C007、C009—C010 和 platforms/xiaohongshu.json，保留来源状态与日期。https://github.com/huangbai-AI/guoshen

上游原创许可证分别保留在子目录。上游引用的法规与平台原文不因此重新授权；当前仅收录原创模式及规则摘要，不复制法规长文。不把第三方标注 official 当成本项目已核官方结论。

本项目自写 publish_precheck.py 适配层；不运行上游脚本、不上传稿件到这两个项目、不自动拉取新规则。语义检查使用工作台原有模型配置。更新时核对上游差异、日期、适用范围并运行测试，修改固定版本记录；不得无审核覆盖。
