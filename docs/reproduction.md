# 公开快照复现记录

日期2026-11-07，Asia/Shanghai；实际平台macOS26.6.2 ARM64，Python3.14.3、JDK21.0.10、Node24.14.0。源码快照和运行工作区分离；没有使用原项目.venv、测试库或Day14代码。

| 检查 | 实际结果 |
|---|---|
| 全新venv安装requirements-ui（包含后端锁定依赖） | PASS，pip check无冲突 |
| Quick Start API/storage真实HTTP | 82 passed，退出0 |
| 改版CI runner prepare/api | PASS，另立干净结果目录 |
| API服务与数据清理 | 6个成功服务数据库三表为0、foreign_key_check空、服务退出0 |
| 官方Wrapper来源/摘要 | PASS，Gradle固定8.13，JAR与分发校验值有记录 |
| 独立Gradle缓存构建公开源码 | BUILD SUCCESSFUL，35任务执行，退出0 |
| 安装新构建APK | Success |
| 新驱动目录+新APK真实UI | 6 passed，退出0 |
| Session与Appium清理 | 6次quit、6次DELETE 200，所属Appium正常停止 |
| Allure HTML与真实截图 | 88 passed，生成退出0，浏览器实际核对 |
| JMeter新health/replay | 各3样本0失败；重放主空间1笔；清理通过 |
| Groovy语法、Python与Shell语法 | PASS |
| 新Jenkins Declarative验证/实际构建 | **NOT VERIFIED** |
| JMeter归档全新网络下载 | **NOT VERIFIED**，使用匹配新官方SHA512的已有发行归档独立解压 |
| 另一台干净电脑/Linux/Windows | **NOT VERIFIED** |
| 远程仓库、GitHub Pages | 未创建/部署，阶段A不发布 |
| 项目自身开源许可 | 验证时尚未选择；2026-11-09经确认对原创内容添加MIT（2026 ziozn），第三方原许可保留 |

[机器可读摘要](evidence/verification-summary.json)、[API清理](evidence/api-cleanup.json)、[UI清理](evidence/ui-session-cleanup.json)、[Wrapper来源](evidence/wrapper-provenance.json)。

首次沙箱内API/JMeter因无法绑定回环端口失败；按本机执行权限复验后通过。失败日志本机保留，不混入公开报告。首次已安装APK的UI6 passed作为准备记录，最终公开UI证据采用新构建APK的独立第二次执行，两轮不相加。

首次Gradle默认入口下载很慢，后续完成校验和构建；其他超时的下载重试保留为失败，不使用未完成文件。Allure报告用不同时间执行的API和最终UI合并，报告跨度包含准备时间，不是纯测试执行时长。真实CI runner成功与Jenkins插件/DSL运行是不同验证层级。

公开版本与原版差异仅部署适配：当前解释器、相对输出目录、可配置UDID/工具目录、可选平台诊断、工作区Jenkins配置、Wrapper和展示文档。所有service与Android业务源码逐字相同，正式测试208处assert的AST保持一致。原仓库和Day14文件摘要已在私有验收记录中核对。


## 2026-11-09本地发布准备
只迁移阶段A白名单文件、添加已确认MIT许可证并更新发布说明/清单，没有修改Python、Kotlin、JMX、Groovy、依赖或构建配置。可执行文件与2026-11-07已验证候选的SHA-256一致，因此沿用上述真实结果，不宣称2026-11-09重新执行回归。docs/evidence/verification-summary.json保留验证当天的状态，包括当时尚未选择许可、尚未建立Git历史的记录。

新的独立main历史不含原仓库历史。首次提交身份由所有者确认为ziozn及GitHub noreply邮箱；未配置远程或推送。新增LICENSE和文档更新不改变业务语义。
