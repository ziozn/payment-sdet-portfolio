# 架构与关键源码

## 后端与数据
[main.py](../service/main.py)定义路由与严格输入模型；[database.py](../service/database.py)管理SQLite事务/约束；[迁移脚本](../service/migrate_database.py)仅支持已知旧用户表的显式离线迁移。初始化不静默删除旧库。

[API fixture](../tests/api/conftest.py)用当前解释器启动真实Uvicorn，生成独立库与动态端口。每例唯一空间；teardown按空间删除用户、外键级联，核对三表和foreign_key_check，只操作专用库。

[支付测试](../tests/api/test_payments.py)核对HTTP、业务字段和数据库。重放、参数冲突、并发同键、拒付后重试、其他空间同键互不影响均有正式用例。存储测试覆盖唯一性、外键、回滚与迁移。

## Android与Page Object
[HomePage](../tests/ui/pages/home_page.py)与[PaymentPage](../tests/ui/pages/payment_page.py)封装resource-id、显式等待和操作，assert留在[测试层](../tests/ui)。新Activity不保留上次结果；空EditText的hint通过实际XML标志区分。

[android_driver](../tests/ui/conftest.py)每例真实Session，finally保存现场并quit；取证失败仍尝试quit。ui_case记录测试异常后原样抛出，不把普通yield fixture当作能收到测试主体异常的上下文管理器。

App只显示金额，明确“未调用后台API”“交易ID未生成”，不含网络支付调用。

## 编排与实验
[Jenkinsfile](../Jenkinsfile)在正常SCM工作区准备环境、跑API/storage，FULL再跑UI。runner拒绝接管占用端口，只停止自己创建的Appium。post分别尝试清理、Allure、JUnit和归档。公开改版是否已在Jenkins执行以[CI记录](ci-demo.md)为准。

[JMeter runner](../performance/jmeter/run.py)为每次实验新建专用服务/库，执行JMX，再核对记录、返回ID和其他空间，最后清理；[分析器](../performance/jmeter/analyze.py)从真实JTL计算指标。读取RPS与新增支付TPS分开解释。
