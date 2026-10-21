# 贡献指南

欢迎改进文档、确定性字段处理、平台适配和离线测试。

1. Fork 仓库并创建主题分支，改动保持集中。
2. Issue 写明模块、预期行为、实际行为和脱敏后的复现步骤。
3. Pull request 说明改动目的、验证命令及已知限制；保留原作者和第三方声明。
4. 不提交真实候选人、聊天记录、账号 Cookie、个人浏览器目录、内部服务标识、配置后的源码或运行日志。
5. 测试优先使用合成数据及 mock；不要让普通测试默认发送真实消息或上传人才数据。

扩展测试：`node --test apps/extension/tests/*.test.js`。

猎聘学历规则测试：在 `apps/liepin` 执行 `python3 -m unittest discover -s tests -p test_highest_education.py`。

贡献按项目 Apache-2.0 许可证提交。第三方材料需保留适用许可证。安全问题通过仓库 Security 页的私密报告渠道提交。
