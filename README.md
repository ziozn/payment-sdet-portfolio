# 模拟支付 SDET 自动化作品集

一个可核对源码、断言与执行证据的个人学习项目：FastAPI + SQLite 模拟后端，PyTest/Requests 验证 HTTP 与数据一致性；独立 Android App 用 Appium/UiAutomator2 验证界面；Jenkins 编排回归并发布 JUnit/Allure；JMeter 做有限本机性能实验。

**边界：Android 不调用 FastAPI，不创建后台支付交易；全部 DEMO 数据不涉及真实资金。本项目由 Codex 辅助开发，不包含公司内部源码，也不代表本人已独立掌握全部实现。**

## 四个展示入口

- [代码与 Quick Start](README.md)
- [Jenkins / CI 配置与历史构建记录](docs/ci-demo.md)
- [Allure 报告截图与执行来源](docs/allure-report.md)
- [JMeter 脚本、指标与实验限制](docs/performance-report.md)

四个入口均为仓库内实际文件，公开仓库地址为 [ziozn/payment-sdet-portfolio](https://github.com/ziozn/payment-sdet-portfolio)。报告保留真实执行日期；Jenkins新配置的未验证状态见对应文档。

## 实现与代码导航

| 范围 | 已实现与核对点 |
|---|---|
| 模拟业务 | 创建/查询用户 → 固定DEMO实名 → 绑虚构卡 → 支付/查询；金额为整数分1..1,000,000；仅记录SUCCEEDED |
| HTTP自动化 | [API tests](tests/api)、[storage tests](tests/storage)；真实Requests、响应字段、GET、SQLite记录与约束 |
| Fixture | [conftest](tests/api/conftest.py)启动独立服务/库；每例唯一空间，外键级联清理 |
| 支付幂等 | 同空间同键同参数返回同交易和201；参数变化409；BEGIN IMMEDIATE + UNIQUE |
| Android UI | [App源码](android-app)、[PO](tests/ui/pages)、[UI tests](tests/ui)；金额/非法输入/二次进入初态/Session隔离 |
| CI / 报告 | [Jenkinsfile](Jenkinsfile)、[runner](scripts/ci_runner.py)；失败退出传播、JUnit、Allure HTML、取证与清理 |
| 性能实验 | [JMX与分析器](performance/jmeter)；读取阶梯及少量支付新键/重放/冲突，最终数据库核对 |

~~~mermaid
flowchart LR
  CI[Jenkins] --> API[PyTest + Requests]
  API --> BE[本机 FastAPI]
  BE --> DB[(隔离 SQLite)]
  CI --> UI[PyTest + Page Object]
  UI --> AS[Appium + UiAutomator2]
  AS --> APP[Android UI 演示]
  API --> R[JUnit / Allure]
  UI --> R
  JM[JMeter 独立实验] --> BE
~~~

Android与FastAPI之间没有业务连线。退款、真实通道、Android/API联调、iOS/真机矩阵均未实现，列为未来计划。见[当前契约](docs/current-contract.md)和[架构](docs/architecture.md)。

## Quick Start：先运行后端

在克隆/解压后的项目根目录执行。脚本支持macOS/Linux POSIX Shell；实际平台与结果见[复现记录](docs/reproduction.md)，Windows原生脚本未验证。

Python **3.14.3**。后端不需要Android、JDK、Appium或Allure CLI。

~~~sh
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest tests/api tests/storage -v --tb=short --junitxml=artifacts/quickstart/api.xml --alluredir=artifacts/quickstart/allure-results
~~~

自动化会初始化新库、选择空闲回环端口、启动Uvicorn，结束后清理数据并停止自己的服务。无需手工启动后端。X-Test-Run-ID是测试分区，不是鉴权。服务证据在artifacts/api-service/service-*/；运行产物默认忽略。

手动观察API时，在独立终端执行：

~~~sh
mkdir -p artifacts/manual
PAYMENT_DB_PATH="$PWD/artifacts/manual/demo.db" .venv/bin/python -m uvicorn service.main:app --host 127.0.0.1 --port 8001
~~~

浏览器访问http://127.0.0.1:8001/docs，或另开终端执行curl http://127.0.0.1:8001/health。Ctrl+C停止服务。手动库会保留，不能当作自动化清理证据。旧库需停服、备份及[显式迁移](service/migrate_database.py)。

## Android、CI与JMeter

- [Android完整步骤](docs/android.md)：Gradle Wrapper、SDK/AVD、构建安装、Appium与UI执行。
- [CI配置与参数](docs/ci-demo.md)：API_ONLY为后端，FULL增加独立UI演示。
- [Allure](docs/allure-report.md)：CLI生成/本机查看，截图与统计注明日期。
- [JMeter](docs/performance-report.md)：固定5.6.3，先3样本Smoke，读取RPS不等于新增支付TPS。
- [5分钟核验路线](docs/demo-guide.md)。

手动故意失败探针仅验证失败传播和取证，默认不收集，不属于未完成用例；详见CI说明。

## 结果与限制

2026-11-07公开候选的验证结果见[复现记录](docs/reproduction.md)与[精简证据](docs/evidence)。2026-11-09本地发布准备仅添加许可证并更新说明和清单，可执行代码、依赖及构建配置与已验证候选逐字一致；未把历史结果称为本日复跑。历史Jenkins #7 API_ONLY 82 passed、#8 FULL 88 passed来自2026-10-31；历史性能来自2026-10-29。不用历史结果证明改版Jenkins或其他电脑已通过。

SQLite单机串行写，同机负载发生器、短窗口、单模拟器串行，不代表生产容量或SLA。未测另一台干净电脑；SDK/AVD为预装工具。公开快照不含个人Git历史、考核骨架、缓存、APK、数据库和完整日志。

## 发布与许可

[公开清单](docs/public-files.txt)、[排除范围](docs/exclusions.md)、[安全审计](docs/security-audit.md)、[第三方许可](THIRD_PARTY_NOTICES.md)随快照提供。项目中有权授权的原创内容采用 [MIT License](LICENSE)，Copyright (c) 2026 ziozn。Gradle Wrapper等第三方组件保留原许可证与版权声明，MIT不覆盖或重新授权这些第三方权利；具体范围见[第三方许可](THIRD_PARTY_NOTICES.md)。
