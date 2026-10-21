# ChatBot 返回格式与解析规范

> 适用项目：`SessionAutoGen-new`、`liepin-helper-api`、`TalentMatch-Extension-New`、`MaimaiHelper`、`ZhiLianAuto`
>

## 1. 使用方式

1. 按 `chatbotID` 或用途查找对应契约。
2. 修改 Prompt 时保留表中规定的关键词、字段名、标点和数据类型。
3. 如需改变返回格式，先修改并验证所有消费端，再更新本文。

本文不记录无法从源码确认的底层模型。`chatbotID` 只是 AnyHelper 后台 Bot 配置标识。

## 2. 通用 HTTP 响应

AnyHelper Chatbot 接口：

```text
POST https://model.example.invalid/api/completions/quora.php
```

调用方通常读取：

```javascript
data.choices?.[0]?.message?.content
```

因此外层响应至少需要满足：

```json
{
  "choices": [
    {
      "message": {
        "content": "Chatbot 返回内容"
      }
    }
  ]
}
```

除非下文明确要求 JSON、整数或 ID 列表，否则 `message.content` 应为非空纯文本。

## 3. 共享核心契约

| 用途        | Chatbot ID                         | 返回格式                            | 主要消费项目            |
| --------- | ---------------------------------- | ------------------------------- | ----------------- |
| 初筛/首次匹配   | `__TALENTMATCH_MODEL_05__` | 必须包含 `非常匹配`、`匹配`、`不确定` 或 `不匹配`  | 五个项目              |
| 事实判断/二次复核 | `__TALENTMATCH_MODEL_06__` | 中文逗号分隔的固定句式                     | 五个项目              |
| 清洗简历      | `__TALENTMATCH_MODEL_08__` | 固定 Markdown 字段                  | 多项目               |
| 格式化简历     | `__TALENTMATCH_MODEL_07__` | 固定 Markdown 字段                  | TalentMatch       |
| 简历摘要      | `__TALENTMATCH_MODEL_19__` | 非空纯文本；MaimaiHelper 还读取薪资、居住地和标签 | 多项目               |
| 策略名称      | `__TALENTMATCH_MODEL_14__` | 简短单行文本                          | 多项目               |
| 简历翻译      | `__TALENTMATCH_MODEL_30__` | Markdown，以独立一行 `---` 分区         | 多项目               |
| 薪资清洗      | `__TALENTMATCH_MODEL_31__` | 单个薪资值，如 `20K-30K/月`             | 多项目               |
| 聊天文本标签    | `__TALENTMATCH_MODEL_29__` | 允许标签，多个用英文逗号分隔                  | 多项目               |
| 会话状态标签    | `__TALENTMATCH_MODEL_22__` | 可被 `int()` 解析的纯整数               | 多项目               |
| 普通自动回复    | `__TALENTMATCH_MODEL_24__` | 可直接发送的单条纯文本                     | 多项目               |
| 猎头模式回复    | `__TALENTMATCH_MODEL_34__` | 可直接发送的单条纯文本                     | liepin-helper-api |
| 二次联系      | `__TALENTMATCH_MODEL_23__` | 可直接发送的单条纯文本                     | 多项目               |

### 3.1 初筛

推荐格式：

```text
判断结果：非常匹配，原因：候选人……
判断结果：匹配，原因：候选人……
判断结果：不确定，原因：简历中缺少……
判断结果：不匹配，原因：候选人……
```

注意：

- `SessionAutoGen-new` 主要检查开头约 15 个字符，结论应放在最前面。
- 部分代码只检查是否包含“不匹配”；没有标准状态词时可能被误判为通过。
- 不要用“符合”“建议通过”或数字评分替代状态词。
- 不要出现“并非不匹配，最终为匹配”这类同时包含相反状态的表达。

### 3.2 事实判断

推荐格式：

```text
是，判断合理，确实非常匹配，原因……
是，判断合理，确实匹配，原因……
是，判断合理，确实不确定，缺失信息……
否，不合理，判断结果应为不匹配，原因……
```

消费端会按中文逗号 `，` 分割，并识别“确实”或“判断结果应为”。不要改成英文逗号或删除前述结构。

### 3.3 清洗/格式化简历

必须保留以下字段名：

```markdown
# 候选人姓名：张三

**年龄**：35岁
**性别**：男
**期待薪资**：25K-35K/月
**居住地**：上海
**优势标签**：财务管理、成本管控、团队管理

**推荐语**：
具有相关行业和岗位经验。

---

## 工作经历
……
```

常用正则：

```regex
\*\*推荐语\*\*[:：]?\s*([\s\S]*?)(?:\n---|\n##|$)
\*\*期待薪资\*\*[:：]?\s*(.+)
\*\*居住地\*\*[:：]?\s*(.+)
\*\*优势标签\*\*[:：]?\s*(.+)
```

TalentMatch 的部分正则要求中文冒号和推荐语后的 `---`，因此不要修改字段名、粗体标记或分隔线。

### 3.4 聊天标签

允许的文本标签：

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

数字状态标签必须只返回整数。当前明确使用的值：

| ID    | 含义    |
| -----:| ----- |
| `104` | 在职急寻  |
| `105` | 在职看机会 |
| `107` | 离职    |
| `109` | 需再联系  |
| `110` | 不跳槽   |
| `256` | 强意向   |

自动回复内容会直接发给候选人，不要包含模型说明、多个方案、JSON 或代码围栏。

## 4. SessionAutoGen-new

| 用途      | Chatbot ID                         | 返回契约                           |
| ------- | ---------------------------------- | ------------------------------ |
| 岗位要求解析  | `ZE1aLzJUTkhPYnd3ZEpVYmx4UzFvZz09` | 每行至少 6 个竖线分隔字段                 |
| 岗位信息解析  | `MFAwRmFPbXA5MVF6YmNTVDBjc0NmZz09` | 与 `Analysis` 数据结构匹配的合法 JSON 对象 |
| 动态调节决策  | `V09Kb21DbHhvQ2oxRGVJbUVNSi9uQT09` | JSON，必须包含 `action` 和 `data`    |
| 公司范围转名称 | `N2dwOGRRWExrU0hxeXUrMG56ZU1SQT09` | 空格分隔的公司关键词                     |

岗位要求解析模板：

```text
Must1|product|核心产品|光伏 储能|光伏 储能|FALSE
Nice1|skill|加分技能|英语|英语|TRUE
职位类型：销售
```

动态调节模板：

```json
{
  "action": "动作名称",
  "data": {}
}
```

### liepin-job-publisher 岗位清洗

该流程使用可切换的 OpenAI/Anthropic 兼容模型，不通过固定 `chatbotID`。结果必须通过以下 JSON Schema：

```json
{
  "companyName": "上海某某科技有限公司",
  "companySearchKeywords": ["某某科技", "上海某某"],
  "categoryIndex": 1,
  "cityIndex": 1,
  "educationKeyword": "本科",
  "workYearLow": 3,
  "workYearHigh": 5,
  "recruitCnt": 1,
  "confidence": "high",
  "cleanNotes": ["公司名已清洗"],
  "warnings": []
}
```

约束：

- `companySearchKeywords` 为 1–3 项。
- `categoryIndex`、`cityIndex` 大于 0。
- `educationKeyword` 为 `不限/中专/大专/本科/硕士/MBA/博士`。
- `workYearLow`、`workYearHigh` 为 0–99，`recruitCnt` 为 1–99。
- `confidence` 为 `high/medium/low`。
- 不得缺字段、改字段名、使用中文数字或返回多个 JSON 对象。

## 5. liepin-helper-api / ZhiLianAuto 搜索策略

| 用途        | Chatbot ID                         | 返回契约                  |
| --------- | ---------------------------------- | --------------------- |
| 快速策略      | `__TALENTMATCH_MODEL_25__` | 固定五行字段                |
| 随机策略      | `__TALENTMATCH_MODEL_26__` | 固定三行关键词字段             |
| 深匹策略      | `__TALENTMATCH_MODEL_27__` | 固定字段逐行返回              |
| 猎聘首次沟通候选人 | `__TALENTMATCH_MODEL_32__` | 英文逗号分隔的 `resIdEncode` |
| 子岗位问题判断   | `__TALENTMATCH_MODEL_33__` | 只能返回 `是` 或 `否`        |
| 智联首次沟通候选人 | `__TALENTMATCH_MODEL_28__` | 英文逗号分隔的 `resumeK`     |

快速策略：

```text
学历要求：本科
年龄要求：25-40
工作年限：3-10
薪资要求：20-40
工作地点：上海 北京
```

随机策略：

```text
简历描述关键词：光伏 储能 海外销售
职位关键词：海外销售总监 国际销售总监
公司名称关键词：新能源 科技 能源
```

深匹策略可识别字段：

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

这些解析器依赖中文冒号 `：`，多个值用半角空格分隔。无结果使用固定文本 `无有效信息`。

候选人 ID 列表使用英文逗号分隔，不要返回 JSON 数组、字段名或解释。无结果返回空字符串。

> 已知问题：`ZhiLianAuto` 的年龄上限解析存在 `.stirp()` 拼写错误；这是消费端问题，Prompt 无法规避。

## 6. TalentMatch-Extension-New

| 用途                | Chatbot ID                         | 返回契约               |
| ----------------- | ---------------------------------- | ------------------ |
| 列表候选人筛选           | `__TALENTMATCH_MODEL_04__` | JSON 字符串数组         |
| 猎聘搜索关键词           | `__TALENTMATCH_MODEL_09__` | 固定三行字段             |
| LinkedIn 搜索 URL   | `__TALENTMATCH_MODEL_10__` | 包含完整 URL，最好只返回 URL |
| 旧 LinkedIn 搜索 URL | `__TALENTMATCH_MODEL_11__` | 已注释，不是当前调用         |
| 扩展策略名称            | `__TALENTMATCH_MODEL_01__` | 简短单行名称             |
| 公司全称              | `__TALENTMATCH_MODEL_17__` | 只返回公司全称            |
| BOSS 岗位整理         | `__TALENTMATCH_MODEL_16__` | 干净的岗位要求文本          |
| 岗位/公司信息整理         | `__TALENTMATCH_MODEL_18__` | 干净的岗位要求文本          |
| 平台专用匹配            | `__TALENTMATCH_MODEL_12__` | 使用共享状态词            |
| 平台专用匹配            | `__TALENTMATCH_MODEL_13__` | 使用共享状态词            |
| 平台专用匹配            | `__TALENTMATCH_MODEL_15__` | 使用共享状态词            |
| LinkedIn 公司分析     | `__TALENTMATCH_MODEL_02__` | 简短纯文本              |
| LinkedIn 公司判断     | `__TALENTMATCH_MODEL_03__` | 建议以 `是` 或 `否` 开头   |
| LinkedIn 动态总结     | `__TALENTMATCH_MODEL_20__` | 完整总结文本             |
| 选中文本分析            | `__TALENTMATCH_MODEL_21__` | 非空纯文本              |

列表筛选：

```json
["张三", "李四"]
```

无结果：

```json
[]
```

消费端会直接执行 `JSON.parse(content)`，不能增加解释文字或改成 `{"names":[]}`。

猎聘关键词：

```text
简历描述关键词：会计师事务所 审计经理 CPA 团队管理
职位关键词：海外财务经理 财务总监 审计经理
行业关键词：新能源
```

允许的行业名称：

```text
AI/互联网/IT
电子/通信/半导体
房地产/建筑
金融
消费品
机械/制造
教育培训/科研
能源/化工
新能源
生物医药/医疗
汽车
交通/物流/仓储
贸易/进出口
专业服务
```

LinkedIn URL 通过 `/https?:\/\/[^\s]+/` 提取，URL 后不要紧跟中文标点或 Markdown 括号。

## 7. MaimaiHelper

| 用途     | Chatbot ID                         | 返回契约             |
| ------ | ---------------------------------- | ---------------- |
| 批量简历预筛 | `__TALENTMATCH_MODEL_35__` | 英文逗号分隔的数字 UID    |
| 首次匹配   | `__TALENTMATCH_MODEL_05__` | 共享初筛状态词          |
| 二次复核   | `__TALENTMATCH_MODEL_06__` | 共享事实判断格式         |
| 清洗简历   | `__TALENTMATCH_MODEL_08__` | 共享 Markdown 字段   |
| 简历摘要   | `__TALENTMATCH_MODEL_19__` | 摘要并保留薪资、居住地、优势标签 |

UID 示例：

```text
123456,234567,345678
```

每一项都会执行 `int(uid)`。无结果返回空字符串，不要返回 `[]`。

`MaimaiHelper` 对二次复核执行 `split('，')`，对清洗简历的推荐语正则直接调用 `.group(1)`；缺少中文逗号或 `**推荐语**` 会导致解析失败。

## 8. ZhiLianAuto

智联复用共享初筛、事实判断、简历清洗、摘要、翻译、聊天标签、薪资和自动回复契约。专用内容如下：

| 用途      | Chatbot ID                         | 返回契约              |
| ------- | ---------------------------------- | ----------------- |
| 首次沟通候选人 | `__TALENTMATCH_MODEL_28__` | 英文逗号分隔的 `resumeK` |
| 快速策略    | `__TALENTMATCH_MODEL_25__` | 第 5 节固定字段         |
| 随机策略    | `__TALENTMATCH_MODEL_26__` | 第 5 节固定字段         |
| 深匹策略    | `__TALENTMATCH_MODEL_27__` | 第 5 节固定字段         |

首次匹配没有单独识别“不确定”，最好只返回 `非常匹配`、`匹配` 或 `不匹配`。

自动回复中的 `不回复` 是控制词：返回内容只要包含该子串就会跳过发送。需要跳过时仅返回：

```text
不回复
```

正常回复中不要出现该词。

## 9. 统一格式规则

| 返回类型        | 规则                        |
| ----------- | ------------------------- |
| 状态判断        | 使用固定状态词，结论前置              |
| 事实判断        | 使用中文逗号和固定四段结构             |
| Markdown 简历 | 保留字段名、粗体标记和 `---`         |
| JSON        | 只返回合法 JSON，不附加说明或代码围栏     |
| 整数          | 只返回数字                     |
| ID 列表       | 使用英文逗号，不加引号、方括号或字段名       |
| 策略字段        | 一行一个字段，保留原字段名和中文冒号        |
| 自动回复        | 只返回一条可直接发送的纯文本            |
| 名称/文件名      | 单行、简短，不含斜杠、反斜杠、冒号等路径特殊字符    |

## 10. 变更检查

修改 Chatbot Prompt 或返回格式前，确认：

- [ ] 已查到对应 `chatbotID` 和所有消费项目。
- [ ] 固定状态词、字段名、标点和分隔符未被改动。
- [ ] JSON、整数和 ID 列表没有被自然语言包裹。
- [ ] 已使用文档示例测试实际返回。
- [ ] 如修改了解析方式，已同步更新所有消费端和本文档。
