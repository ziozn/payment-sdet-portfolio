# 当前业务契约

全部为本机虚构数据，不连接第三方支付。除health外，接口需要X-Test-Run-ID（1–64个字母/数字/下划线/连字符），用于分区而非鉴权。

| 方法与路径 | 输入与结果 |
|---|---|
| GET /health | 200，status=ok |
| POST /users | display_name为DEMO_前缀；201，NEW和UUID |
| GET /users/{id} | 200；未知/其他空间404 |
| POST /users/{id}/verification | 固定DEMO_PERSON_01与DEMO_ID_01；成功VERIFIED；拒绝409 |
| POST /users/{id}/cards | 虚构DEMO_CARD_OK/DEMO_CARD_001或拒付卡；需实名；重复409 |
| GET /users/{id}/cards | 当前用户当前空间；归属不符404 |
| POST /payments | user_id/card_id/amount_cent；合法201/SUCCEEDED |
| GET /payments/{id} | 当前空间交易200；未知/跨空间404 |

金额为严格整数分1..1,000,000；bool、字符串、小数、越界等422。Idempotency-Key为DEMO_加1–59个字母/数字/下划线/连字符。同空间同键同参数重放保留相同资源、完整响应和原201；同键参数变化409；首次失败不写成功交易。拒付卡只触发本地规则。

users/cards/payments依赖外键和空间归属；BEGIN IMMEDIATE保护查重/写入，UNIQUE(test_run_id,idempotency_key)约束唯一性。SQLite仍是单机串行写，不是分布式支付方案。

源码保留未纳入正式回归的/hea辅助健康路由；安装和演示统一使用/health。

未来计划（未实现）：退款、真实认证、真实资金通道、Android/API联调、iOS、生产鉴权和统一请求日志。旧学习设计草案不随公开快照发布。
