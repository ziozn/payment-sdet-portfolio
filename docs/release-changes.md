# 公开版适配说明

原项目未修改；本文件只说明独立快照与稳定正式项目的区别。

| 文件 | 变化与验证 |
|---|---|
| service/、Android app/src/ | 字节相同，不改业务和数据库结构 |
| API conftest | 使用sys.executable、输出改为artifacts/api-service；原断言保持一致；真实82通过 |
| UI conftest | UDID可配置，默认输出artifacts/ui；原断言保持一致；新APK真实6通过 |
| Jenkinsfile | 移除个人路径/customWorkspace，采用SCM工作区及可配置Agent环境；Groovy语法通过，Declarative运行和新构建NOT VERIFIED |
| scripts/ci_runner.py | 当前解释器、相对输出、可配置APPIUM_HOME；API_ONLY不再强制Java；无Git历史快照可执行；缺Allure明确非零；本地生命周期实际验证 |
| start_jenkins.sh | JENKINS_WAR/JENKINS_HOME/JAVA_HOME/JENKINS_PORT可配置，仅回环监听；Shell语法通过，未启动新控制器 |
| JMeter runner | 当前解释器、JMETER_BIN/PATH解析、相对输出、缺少非本平台诊断时记录不可用；业务断言不变；health/replay新Smoke通过 |
| pytest.ini | 默认只收集后端，Android显式指定；不跳过或放宽正式断言 |
| Gradle Wrapper | 新增官方8.13固定版本、JAR摘要、分发SHA256与第三方许可；独立缓存构建成功 |
| README/docs | 用精简说明替代长学习日志；四个入口与实际证据；明确历史/本次/未验证 |
| public artifacts | 仅少量JUnit、机器可读统计、来源摘要与审查截图；无完整原始日志/数据库/采样 |

全部正式测试208处assert的AST与原项目相同。原始版本的逐项排除清单见[excluded-source-files.txt](excluded-source-files.txt)，实际待公开文件见[public-files.txt](public-files.txt)。
