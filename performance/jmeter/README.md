# JMeter入口

见[完整性能报告](../../docs/performance-report.md)。

health.jmx、user-query.jmx、payment.jmx均不需第三方插件。run.py建立专用服务/库、准备数据、执行/分析/核对/清理。analyze.py只读真实JTL。

工具解析顺序：JMETER_BIN、PATH中的jmeter、项目.tools/apache-jmeter-5.6.3/bin/jmeter。输出须为artifacts/performance下全新目录；读取最多20线程/60秒，支付最多100请求。禁止生产或真实通道。
