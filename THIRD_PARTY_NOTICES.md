# 第三方依赖与素材许可

本项目有权授权的原创内容采用 [MIT License](LICENSE)，Copyright (c) 2026 ziozn。下列第三方内容保留各自许可与版权声明，不因根MIT许可证而被重新授权。

Python依赖不随仓库分发，只提供版本清单；完整安装元数据记录见[dependency-licenses.json](docs/evidence/dependency-licenses.json)。这不是法律意见或对所有传递依赖权利的保证。

| Python包 | 版本 | 安装元数据声明许可 |
|---|---|---|
| allure-pytest | 2.16.2 | Apache-2.0 |
| allure-python-commons | 2.16.2 | Apache-2.0 |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| Appium-Python-Client | 5.3.1 | Apache-2.0 |
| attrs | 26.1.0 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| fastapi | 0.143.2 | MIT |
| h11 | 0.16.0 | MIT |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| outcome | 1.3.0.post0 | MIT OR Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pip | 25.3 | MIT |
| pluggy | 1.7.0 | MIT |
| pydantic | 2.14.1 | MIT |
| pydantic_core | 2.50.1 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| PySocks | 1.7.1 | BSD |
| pytest | 9.1.1 | MIT |
| requests | 2.34.2 | Apache-2.0 |
| selenium | 4.46.0 | Apache-2.0 |
| sniffio | 1.3.1 | MIT OR Apache-2.0 |
| sortedcontainers | 2.4.0 | Apache 2.0 |
| starlette | 1.8.0 | BSD-3-Clause |
| trio | 0.34.0 | MIT OR Apache-2.0 |
| trio-websocket | 0.12.2 | MIT License |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| websocket-client | 1.9.2 | Apache-2.0 |
| wsproto | 1.3.2 | MIT |

## MIT范围与第三方例外
- 根MIT仅覆盖权利人有权授权的原创代码、文档和测试数据；不表示取得了外部依赖、品牌或软件界面的权利。
- android-app/gradlew、gradlew.bat和gradle/wrapper/gradle-wrapper.jar保留上游Apache-2.0声明及随附GRADLE-LICENSE中的适用条款，文件与官方固定版本字节一致。
- docs/assets中的图片是本项目真实执行截图；Allure等第三方软件的界面和品牌权利仍由原权利人保留，截图不构成其代码或品牌的MIT授权。
- 依赖仅以锁定版本声明，由安装工具另行取得；未打包第三方Python、Android SDK、Appium、Jenkins、Allure或JMeter二进制。

## 构建和测试工具
- Gradle Wrapper 8.13：从Gradle官方仓库固定tag取得，JAR摘要匹配官方记录。随附[Gradle LICENSE](android-app/gradle/GRADLE-LICENSE)，仅适用于该第三方组件；下载来源和摘要见[Wrapper证据](docs/evidence/wrapper-provenance.json)。
- Android Gradle Plugin与Kotlin：Apache-2.0；仅构建依赖，不分发缓存或SDK。Android SDK和系统镜像需各自安装并遵守上游条款。
- Appium、UiAutomator2、Selenium：Apache-2.0；Jenkins核心MIT，所装插件许可各异，需管理员按插件清单复核；Allure与Apache JMeter为Apache-2.0。工具二进制均不公开。
- 本仓库无第三方图片、图标包或字体资产。报告截图来自实际自有测试数据；保留工具品牌以说明真实来源，不宣称由本人开发Allure或Jenkins。
- Python安装依赖包含certifi（MPL-2.0）等不同许可组件；不把所有第三方组件统称MIT，也不把依赖安装视作授权本项目。
