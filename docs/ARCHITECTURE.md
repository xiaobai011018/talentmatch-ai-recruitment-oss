# 架构与代码导航

## 业务视角

四个应用围绕相同招聘目标，但保留独立入口和各自的平台实现。统一的是岗位与候选人业务语义、外部模型任务以及人才 API，不是统一运行时或完整共享 SDK。

```mermaid
flowchart LR
    JD[岗位需求与策略] --> SEARCH[平台搜索]
    SEARCH --> FILTER[列表预筛]
    FILTER --> MATCH[简历匹配与复核]
    MATCH --> CONTACT[高潜同步 / 首次沟通]
    CONTACT --> CHAT[回复与二次联系]
    CHAT --> INTENT[意向及联系方式识别]
    INTENT --> SAVE[正式人才新增 / 更新]
```

这是一条代表性链路。不同平台、执行模式和跳过条件会改变步骤顺序，不保证所有入口都经历全部阶段。

## 模型层

业务通过 AnyHelper 模型接口提交 prompt 和 chatbotID，消费 `choices[0].message.content`。不同配置负责预筛、匹配、复核、清洗、摘要、翻译、标签、自动回复等任务。

- [脉脉模型适配](../apps/maimai/src/io/bot.py)
- [猎聘模型适配](../apps/liepin/backend/api/chatBotApi.py)
- [智联模型适配](../apps/zhilian/backend/core/api/chatBotApi.py)

输出协议包括逗号分隔 ID、匹配关键词、固定 Markdown 字段和纯整数标签。它们不是统一 JSON Schema，部分异常处理仍不充分。二次复核是一轮模型判断，不是外部事实来源核验。

## 平台执行层

- **扩展：**[manifest](../apps/extension/manifest.json)、[popup](../apps/extension/src/core/popup.js)、[content script](../apps/extension/src/core/content.js) 和 [background](../apps/extension/src/core/background.js) 分别承担加载配置、用户入口、页面操作与后台调度。
- **脉脉：**[Manager](../apps/maimai/src/manager.py) 编排流程，[UserProxy](../apps/maimai/src/io/maimai.py) 与 [UserService](../apps/maimai/src/service/user_service.py) 对接平台操作。
- **猎聘：**[Manager](../apps/liepin/backend/manger.py)、[Candidate](../apps/liepin/backend/entity/candidate.py) 及 [API 适配](../apps/liepin/backend/api/lp.py) 组织搜索、沟通与同步。
- **智联：**[Manager](../apps/zhilian/backend/manger.py)、[Candidate](../apps/zhilian/backend/core/entity/candidate.py) 及 [API 适配](../apps/zhilian/backend/core/api/zhilian_api.py) 处理对应平台业务。

保留原文件名 `manger.py`，本次未进行命名或架构重构。

## 上下文管理

脉脉通过职位卡片、历史线索、会话缓存及触达记录关联岗位，信息不足时跳过；自动回复还检查最后有效发言方、是否在招、是否由 Helper 发起。模型输入结合岗位 JD 与聊天上下文。

智联对自动回复会话范围、在线/附件简历消息、联系方式和规则标签做针对性处理。这些是业务上下文及缓存机制，不是向量记忆或 RAG。

## 状态与恢复

扩展猎聘调度记录 runId、注入索引、活动页面及心跳，使用 Promise 队列串行修改状态并持久化到 Chrome Storage。当前并发注入上限是 2，心跳阈值是 120 秒；超时释放槽位，不保证失败页面自动重跑。

脉脉使用线程锁、Event、线程归属标识及可中断等待控制自动回复，失败上传保留待处理项。Python 模型请求有超时重试，各平台有不同程度的单候选人容错与认证失败处理。

## 数据同步

人才接口由外部服务提供。模块采用平台 ID、简历链接、SmartKeywords、联系方式及岗位维度查重。SmartKeywords 是业务字段的组合和归一化，不是语义向量。

[猎聘上传台账](../apps/liepin/backend/utils/resume_upload_ledger.py) 按 `(position_id, encode_res_id)` 记录成功上传，减少跨任务重复。智联、猎聘分别处理高潜与正式记录状态，避免混用 screening_id 和 resume_id。

以上不等于分布式事务或 exactly-once。文件状态、API 写入及回写之间仍存在部分成功和跨进程竞争风险。

## 数据质量与平台字典

学校和专业按最高学历的同一条教育经历提取，缺失和歧义保留空值。部分沟通标签优先采用规则证据，减少不必要的模型判断。

扩展包含 [字典映射生成工具](../apps/extension/tools/build-recruiting-platform-maps.js)。当前文件统计有 454 个可用猎聘到智联职位映射、69 个可用行业映射；另有未映射或歧义项。数字指映射条目数量，不是业务准确率。

## 已知边界

- 插件策略过滤仍包含基于 JSON/URL 外形的分类；原文档中的 source 隔离和完整 Schema 校验建议不能视为已实现。
- 浏览器扩展包含大文件和重复逻辑，本次保留现状。
- 平台接口及 DOM 可能随平台升级变化。
- 外部模型、业务 API、实际账号和完整端到端环境未随仓库提供。
- 部分日志仍包含详细输入输出；没有完整隐私合规或公网安全保证。
- 未新增自主规划、多 Agent、Function Calling 协议、MCP、RAG、模型微调或分布式任务队列。

建议阅读顺序：模型适配 → Manager 业务流程 → Candidate 与会话解析 → 外部 API → 状态/查重 → 对应测试。原模块 README 和 docs 保留历史上下文，以当前代码为准。
