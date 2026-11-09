# Jenkins / CI配置与真实构建记录

入口：[Jenkinsfile](../Jenkinsfile)、[CI runner](../scripts/ci_runner.py)、[历史插件版本](../ci/plugins.txt)。

API_ONLY执行环境准备、API/storage；FULL再执行独立Android UI演示。两种模式都尝试post清理、Allure、JUnit发布和归档；FULL不是Android到后台支付端到端测试。

## 公开版配置
移除了个人PROJECT_ROOT、customWorkspace、JAVA_HOME、SDK和PATH绝对路径。使用正常SCM工作区和相对命令；Node/Java/AndroidSDK/Python由Agent配置。ANDROID_UDID默认emulator-5554；APPIUM_HOME可配置。无需sudo、关闭安全机制或复制Jenkins Home。

创建Pipeline from SCM，Script Path为根Jenkinsfile，使用POSIX且具备Python3.14.3的Agent。先配置官方Jenkins、Pipeline/Declarative/JUnit插件，再运行API_ONLY；FULL的Agent还需按[Android步骤](android.md)构建安装APK、启动模拟器并装好Appium驱动。Allure CLI是post报告的前置；缺失会令报告步骤非零。历史插件版本只供复核，不保证未来控制器兼容性。

~~~sh
# 在项目根目录，本地验证同一套runner
.venv/bin/python scripts/ci_runner.py prepare --output artifacts/ci/local-demo-01
.venv/bin/python scripts/ci_runner.py api --output artifacts/ci/local-demo-01
.venv/bin/python scripts/ci_runner.py ui --output artifacts/ci/local-demo-01
.venv/bin/python scripts/ci_runner.py cleanup --output artifacts/ci/local-demo-01
.venv/bin/python scripts/ci_runner.py report --output artifacts/ci/local-demo-01
~~~

API_ONLY可省略ui。每次用新输出目录，不混用旧结果。API不需手动服务；ui检查设备/包/驱动，并仅管理自己创建的Appium。

如使用WAR，先从[Jenkins官方](https://www.jenkins.io/download/)下载兼容版本并校验，设置JENKINS_WAR后运行sh scripts/start_jenkins.sh；脚本仅监听回环地址，保持初始设置与认证，不自动创建管理员。Jenkins URL和8080端口仅供本机访问，不是互联网展示地址。

## JUnit、Allure与归档
每个suite写junit.xml、allure-results、真实命令和退出码。Jenkins post逐suite发布JUnit，再归档本次CI_OUTPUT；报告失败不会被SUCCESS掩盖。Allure CLI生成HTML，不要求Jenkins Allure插件。不要公开未审查的完整artifacts。

## 实际验证与历史分开

| 来源 | 日期 | 结果 |
|---|---|---|
| 原配置Jenkins #7 API_ONLY | 2026-10-31 | SUCCESS，82 passed |
| 原配置Jenkins #8 FULL | 2026-10-31 | SUCCESS，82后端+6UI=88 passed |
| 公开快照本地runner | 2026-11-07 | prepare/api/ui/report/cleanup实际执行成功 |
| 改版Jenkinsfile的Groovy语法 | 2026-11-07 | 通过官方Groovy解析 |
| 改版Declarative DSL / 新Jenkins构建 | 本次 | **NOT VERIFIED** |

历史统计从真实JUnit提取，SUCCESS从真实控制台核对；仅保留[脱敏记录及来源SHA-256](evidence/historical-jenkins.json)，没有复制完整日志或含用户信息的截图。新本地runner通过不等于新Jenkins构建通过。

正式采用改版前，管理员应使用[Jenkins官方Declarative Linter](https://www.jenkins.io/doc/book/pipeline/development/#linter)验证，再分别执行API_ONLY/FULL并检查JUnit/Artifacts。不要把凭据发给助手、写进代码或公开命令记录。该项尚未验证的限制随公开文档保留。

## 可选故意失败探针
tests/ui/failure_probe.py和tests/api/allure_failure_demo.py为明确设计的失败验证，默认PyTest收集不运行。只有显式指定或runner probe才执行，用于核对非零退出、失败取证与post归档。它们不属于正式通过率，也不是Day14考核骨架。
