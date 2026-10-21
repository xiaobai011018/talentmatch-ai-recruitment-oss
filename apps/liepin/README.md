> 仓库整理说明：本文保留原模块文档与历史记录；统一运行说明见 [SETUP](../../docs/SETUP.md)，当前能力边界见 [ARCHITECTURE](../../docs/ARCHITECTURE.md)。部分历史演示数据与业务截图已从上传副本移除。

# liepin-helper-api

本文档记录 `liepin-helper-api` 当前使用的 ChatBot、Bot 返回格式以及代码侧的解析约束。修改 AnyHelper 后台 Bot Prompt 时，必须保持下列接口契约，否则可能导致搜索条件解析失败、候选人 ID 无法匹配、简历字段提取为空、标签转换异常，或将模型说明文字直接发送给候选人。

> 本文档描述的是当前代码能够消费的格式。`chatbotID` 是 AnyHelper 后台 Bot 配置标识，不代表可从仓库确认的底层模型名称。

## ChatBot 调用协议

请求地址：

```text
POST https://model.example.invalid/api/completions/quora.php
```

请求以表单形式传递：

```text
prompt=<输入内容>
chatbotID=<Bot 配置标识>
```

HTTP 响应必须是 JSON，并至少包含：

```json
{
  "choices": [
    {
      "message": {
        "content": "ChatBot 实际返回文本"
      }
    }
  ]
}
```

代码固定读取：

```python
payload["choices"][0]["message"]["content"]
```

因此 `choices` 必须是非空数组，第一项必须包含 `message`，且 `message.content` 必须是字符串。修改 Bot Prompt 通常只应改变 `message.content`，不能改变 HTTP 外层协议。

## Bot 总览

| 枚举名 | Chatbot ID | 用途 | 返回格式摘要 |
|---|---|---|---|
| `GET_AI_FAST_STRATEGY` | `__TALENTMATCH_MODEL_25__` | 快速搜索策略 | 5 个固定字段，逐行返回 |
| `GET_AI_RANDOM_STRATEGY` | `__TALENTMATCH_MODEL_26__` | 随机搜索策略 | 3 个固定关键词字段 |
| `GET_AI_DEEP_STRATEGY` | `__TALENTMATCH_MODEL_27__` | 深匹搜索策略 | 固定字段名，逐行返回 |
| `GET_FIRST_CHECK` | `__TALENTMATCH_MODEL_05__` | 候选人初筛 | 必须包含标准匹配状态词 |
| `GET_FACT_CHECK` | `__TALENTMATCH_MODEL_06__` | 事实判断、二次复核 | 中文逗号分隔的至少 4 段文本 |
| `GET_CLEAN_RESUME` | `__TALENTMATCH_MODEL_08__` | 清洗简历 | 含固定加粗字段的 Markdown |
| `GET_SIMPLE_RESUME` | `__TALENTMATCH_MODEL_19__` | 简历摘要 | 非空纯文本 |
| `GET_CLEAN_SALARY` | `__TALENTMATCH_MODEL_31__` | 薪资清洗 | 单个简短薪资值 |
| `GET_FIRST_CONVERSATION_SIMPLE_CHECK` | `__TALENTMATCH_MODEL_32__` | 初次沟通候选人筛选 | `[]` 或英文逗号分隔的 ID |
| `SON_POSITION_QUESTION_CHECK` | `__TALENTMATCH_MODEL_33__` | 子岗位问题判断 | 只能返回 `是` 或 `否` |
| `GET_TAG_BY_CHAT_HISTORY` | `__TALENTMATCH_MODEL_22__` | 会话状态标签 | 可被 `int()` 直接解析的整数 |
| `GET_CHAT_TAGS` | `__TALENTMATCH_MODEL_29__` | 聊天文本标签 | 允许集合中的标签文本 |
| `AUTO_REPLY_MSG_GEN` | `__TALENTMATCH_MODEL_24__` | 普通自动回复 | 可直接发送的单条纯文本 |
| `GET_HUNTER_AUTO_REPLY` | `__TALENTMATCH_MODEL_34__` | 猎头模式自动回复 | 可直接发送的单条纯文本 |
| `SECOND_CONTACT_MSG_GEN` | `__TALENTMATCH_MODEL_23__` | 二次联系消息 | 可直接发送的单条纯文本 |
| `RESUME_TRANSLATOR` | `__TALENTMATCH_MODEL_30__` | 简历翻译 | 使用 `---` 分段的 Markdown |

## 搜索策略

### 快速搜索策略

枚举名：`GET_AI_FAST_STRATEGY`

必须使用以下模板：

```text
学历要求：本科
年龄要求：25-40
工作年限：3-10
薪资要求：20-40
工作地点：上海 北京
```

格式要求：

- 一行一个字段，字段名不能改写；
- 字段和值之间使用中文冒号 `：`；
- 年龄、工作年限和薪资范围使用半角连字符 `-`；
- 多个工作地点使用半角空格分隔；
- 不要返回 Markdown 表格、JSON 或解释文字。

### 随机搜索策略

枚举名：`GET_AI_RANDOM_STRATEGY`

必须使用以下模板：

```text
简历描述关键词：光伏 储能 海外销售
职位关键词：海外销售总监 国际销售总监
公司名称关键词：新能源 科技 能源
```

字段名只能是：

```text
简历描述关键词
职位关键词
公司名称关键词
```

没有可用信息时，对应行可以返回：

```text
无有效信息
```

### 深匹搜索策略

枚举名：`GET_AI_DEEP_STRATEGY`

代码可识别以下字段：

```text
搜索词-产品：
搜索词-核心技能：
搜索词-次要技能：
专业关键词：
岗位-具体名称：
岗位-核心词：
岗位-大类名称：
公司名-企业类型：
公司名-细分行业精准词：
当前行业：
公司名-竞争对手：
搜索词-客户名：
搜索词-市场名：
工作城市：
附近城市：
```

推荐返回：

```text
搜索词-产品：光伏 储能
搜索词-核心技能：海外销售 渠道管理
搜索词-次要技能：英语 商务谈判
专业关键词：国际贸易 市场营销
岗位-具体名称：海外销售总监
岗位-核心词：海外销售
岗位-大类名称：销售管理
公司名-企业类型：新能源企业
公司名-细分行业精准词：光伏 储能
当前行业：新能源 电气机械
公司名-竞争对手：华为 阳光电源
搜索词-客户名：EPC 电力公司
搜索词-市场名：欧洲 中东
工作城市：上海 深圳
附近城市：苏州 杭州
```

必须使用原字段名和中文冒号，一行一个字段；多个关键词、城市和行业使用半角空格分隔。没有可用信息的字段可以返回 `无有效信息`。不要返回 Markdown 表格或 JSON。

## 匹配判断

### 初筛

枚举名：`GET_FIRST_CHECK`

返回文本必须包含下列标准状态词之一：

```text
非常匹配
匹配
不匹配
```

推荐格式：

```text
判断结果：非常匹配，原因：候选人……
```

代码按以下顺序识别：

```text
1. 非常匹配
2. 不匹配
3. 匹配
```

当前代码没有单独识别 `不确定`。不要用“符合”“合适”“建议通过”等同义词替换状态词，也不要在最终结论前出现相反的状态词。

### 事实判断与二次复核

枚举名：`GET_FACT_CHECK`

推荐固定格式：

```text
是，判断合理，确实非常匹配，推荐语或判断原因……
是，判断合理，确实匹配，推荐语或判断原因……
否，不合理，判断结果应为不匹配，原因……
```

必须优先使用中文逗号 `，`，并至少保留 4 段：

```text
第 1 段：是或否
第 2 段：判断合理或不合理
第 3 段：确实XX或判断结果应为XX
第 4 段及以后：原因或推荐语
```

代码会根据 `不匹配`、`非常匹配` 和 `匹配` 设置复核标签，还会使用 `fact_check_comment.split("，")[3:]` 提取原因。不要删除固定分段、改用英文逗号，或返回没有标准状态词的长篇分析。

## 简历处理

### 清洗简历

枚举名：`GET_CLEAN_RESUME`

推荐 Markdown 模板：

```markdown
# 候选人姓名：张三

**年龄**：35岁
**性别**：男
**期待薪资**：25K-35K/月
**居住地**：上海 浦东新区
**优势标签**：财务管理、成本管控、团队管理

**推荐语**：
具有大型制造业财务管理和成本管控经验，具备团队管理能力。

---

## 工作经历
……
```

代码使用以下正则提取字段：

```regex
\*\*推荐语\*\*[:：]?\s*([\s\S]*?)(?:\n---|\n##|$)
\*\*期待薪资\*\*[:：]?\s*(.+)
\*\*居住地\*\*[:：]?\s*(.+)
\*\*优势标签\*\*[:：]?\s*(.+)
```

必须保留 `推荐语`、`期待薪资`、`居住地`、`优势标签` 这四个字段名及两侧的 `**`。优先使用中文冒号，并在推荐语后保留 `---`，避免后续章节被一起提取为推荐语。

### 简历摘要

枚举名：`GET_SIMPLE_RESUME`

返回非空纯文本，例如：

```text
候选人拥有10年财务管理经验，熟悉制造业成本管控，曾管理15人团队。
```

不要返回 HTTP 外层 JSON 的字符串副本、只有 Markdown 代码块标记的内容，或无意义的模型声明。

### 薪资清洗

枚举名：`GET_CLEAN_SALARY`

只返回一个简短、可识别的薪资值，例如：

```text
25K-35K/月
```

返回值会被直接当作清洗后的薪资使用，不要附加解释或多个备选答案。

### 简历翻译

枚举名：`RESUME_TRANSLATOR`

返回使用 `---` 分段的 Markdown，建议格式：

```markdown
# 候选人信息
……

---

## 工作经历
……
```

代码使用 `md_text.split("---")` 拆分内容，并在第一段追加手机号和微信号。不要返回 JSON、代码块外壳或无法阅读的非 Markdown 结构。

## 沟通与标签

### 初次沟通候选人列表

枚举名：`GET_FIRST_CONVERSATION_SIMPLE_CHECK`

无符合候选人时，只返回：

```text
[]
```

有符合候选人时，返回英文逗号分隔的 `resIdEncode`：

```text
resIdEncode1,resIdEncode2,resIdEncode3
```

代码对非空结果直接执行 `content.split(",")`，不会解析 JSON 数组。因此有候选人时禁止返回：

```json
["resIdEncode1", "resIdEncode2"]
```

否则方括号和引号会成为 ID 的一部分，导致无法匹配真实候选人。

### 子岗位问题判断

枚举名：`SON_POSITION_QUESTION_CHECK`

只能返回：

```text
是
```

或：

```text
否
```

代码仅在 `bot_reply == "是"` 时返回 `True`。`是的`、`答案：是`、`是，候选人已经回答` 都会被当作 `False`。

### 会话状态整数标签

枚举名：`GET_TAG_BY_CHAT_HISTORY`

必须只返回一个能够被 `int()` 直接解析的整数，例如：

```text
256
```

禁止返回：

```text
标签：256
256（强意向）
{"tag": 256}
```

### 聊天文本标签

枚举名：`GET_CHAT_TAGS`

只能使用以下标签：

```text
地点不考虑
薪资不符合
岗位不匹配
不感兴趣
未读消息
已读不回
有意向沟通
被联系过了
不看机会
```

推荐只返回一个最准确的标签：

```text
有意向沟通
```

代码也兼容以英文逗号或中文逗号分隔的多个标签，但最终只会按业务优先级选取一个合法标签。不要返回 JSON 数组、编号列表、标签解释或集合外的新标签；没有有效标签时，代码回退为 `被联系过了`。

### 自动回复与二次联系

以下 Bot 的返回内容会直接发送给候选人：

| 用途 | 枚举名 | Chatbot ID |
|---|---|---|
| 普通自动回复 | `AUTO_REPLY_MSG_GEN` | `__TALENTMATCH_MODEL_24__` |
| 猎头模式自动回复 | `GET_HUNTER_AUTO_REPLY` | `__TALENTMATCH_MODEL_34__` |
| 二次联系消息 | `SECOND_CONTACT_MSG_GEN` | `__TALENTMATCH_MODEL_23__` |

必须返回一条可以直接发送给候选人的纯文本。不要返回：

- “以下是建议回复”等说明；
- JSON；
- 多个候选回复方案；
- Markdown 代码块；
- 模型思考过程。

## v1.12.24 高潜上传新增学校和专业字段

新增高潜调用 `add_screening_resume.php` 时，Helper 会同时发送 `school` 和 `major`。
两字段直接从 `rawResume.base.eduExpFormList`（兼容 `eduExperiences`）的
`redSchool`、`redSpecial`、`redDegreeName` 提取，不增加 ChatBot 调用，也不依赖简历清洗 Prompt。

- 按可识别的最高学历选择同一条教育经历，同级保持原顺序，与插件的学历优先级一致。
- 缺失学校或专业时对应字段为空，不从其他经历补齐；只有一条有效经历时允许学历未知，多条均无法识别学历时两字段留空。
- 仅影响新增高潜的上传参数，不修改 `Candidate.schoolName`、`Candidate.major`、`smart_keywords`、`liepin_keywords`，不回填已有高潜，也不修改正式人才上传和聊天回写。
- 策略、Excel 初次会话及复用这些入口的全自动流程共用该上传逻辑，无需前端或 Bot 配置变更。

回归测试见 `tests/test_highest_education.py`、`tests/test_screening_education_upload.py`。

## 维护说明

Bot ID 的代码定义位于 `backend/config/chatBotApiConfig.py`，调用与外层响应解析位于 `backend/api/chatBotApi.py`。修改 Bot、Prompt 或解析逻辑时，应同步检查并更新本文档。
