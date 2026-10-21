# 自有服务配置

开源版没有提供原业务模型、提示词服务、人才库后端和数据库。默认外部业务地址使用 `.invalid` 保留域名；不会连接原公司的模型或人才服务。

本地离线测试不需要这些服务。要连接真实服务，需要自行实现兼容的请求和响应协议，或修改各模块适配器。仅有 OpenAI API key 不能直接替代本项目的历史模型服务协议。

## 配置步骤

1. 复制 `config.example.json` 为 `config.local.json`，该文件已加入忽略规则。
2. 将示例域名替换成自己的服务源地址；填写实际使用任务的模型 ID 和调用用户 ID。未使用的任务可留空。
3. 从仓库根目录运行 `python3 tools/configure_services.py config.local.json`。
4. 检查本地差异，再按 [SETUP.md](SETUP.md) 启动对应模块。

配置工具只做明确占位符替换。它不会验证服务可用性，不会发送网络请求，也不会修改凭证的管理方式。不要把配置后的源码、账号标识或配置文件提交到公开仓库。更新配置前请先恢复干净源码或在新副本中操作。

Chrome 扩展、Python 模块和各应用内文档保留历史接口路径以便适配；外部服务需支持相应协议。默认示例域名不能用于生产。

## 模型任务索引

| 配置占位符 | 代码中的任务名称 |
|---|---|
| `__TALENTMATCH_MODEL_01__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_02__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_03__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_04__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_05__` | GET_FIRST_CHECK, MATCH_CHECK_FIRST |
| `__TALENTMATCH_MODEL_06__` | GET_FACT_CHECK, MATCH_CHECK_SECOND |
| `__TALENTMATCH_MODEL_07__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_08__` | CLEAN_SCREENING_RESUME, GET_CLEAN_RESUME |
| `__TALENTMATCH_MODEL_09__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_10__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_11__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_12__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_13__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_14__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_15__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_16__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_17__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_18__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_19__` | AI_SUMMARY_RESUME, GET_SIMPLE_RESUME |
| `__TALENTMATCH_MODEL_20__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_21__` | 浏览器扩展专用模型任务 |
| `__TALENTMATCH_MODEL_22__` | GET_TAG_BY_CHAT_HISTORY |
| `__TALENTMATCH_MODEL_23__` | SECOND_CONTACT_MSG_GEN |
| `__TALENTMATCH_MODEL_24__` | AUTO_REPLY_MSG_GEN |
| `__TALENTMATCH_MODEL_25__` | GET_AI_FAST_STRATEGY |
| `__TALENTMATCH_MODEL_26__` | GET_AI_RANDOM_STRATEGY |
| `__TALENTMATCH_MODEL_27__` | GET_AI_DEEP_STRATEGY |
| `__TALENTMATCH_MODEL_28__` | GET_FIRST_CONVERSATION_SIMPLE_CHECK |
| `__TALENTMATCH_MODEL_29__` | CANDIDATE_TAGS_GEN, GET_CHAT_TAGS |
| `__TALENTMATCH_MODEL_30__` | RESUME_TRANSLATOR |
| `__TALENTMATCH_MODEL_31__` | GET_CLEAN_SALARY |
| `__TALENTMATCH_MODEL_32__` | GET_FIRST_CONVERSATION_SIMPLE_CHECK |
| `__TALENTMATCH_MODEL_33__` | SON_POSITION_QUESTION_CHECK |
| `__TALENTMATCH_MODEL_34__` | GET_HUNTER_AUTO_REPLY |
| `__TALENTMATCH_MODEL_35__` | RESUME_BATCH_PRE_CHECK |
| `__TALENTMATCH_USER_01__` | 外部模型服务调用用户标识 |
