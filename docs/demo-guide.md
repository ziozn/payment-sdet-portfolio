# 面试官5分钟核验路线

1. 看README架构，确认Android与后端独立、全部DEMO数据及Codex辅助开发声明。
2. 按Quick Start跑后端；解释API fixture的独立库、生命周期与空间清理，看真实JUnit和退出码。
3. 看test_payments.py的重放/冲突/并发与数据库断言。仅201不能证明没有第二笔。
4. 看PO和test_navigation.py，按android.md运行真实界面；初态/金额/Session证明UI能力，不证明后台扣款。
5. 看CI、Allure和性能文档，区分历史/本次。吞吐平台是观测，根因尚未受控验证。

环境失败时保留输出，不放宽断言、删除失败或将历史当成现场通过。本人能力需独立解释或编写，不能从协作作品推断。
