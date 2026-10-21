# MaimaiHelper ChatBot 返回格式规范

> 最后更新：2026-08-31
>
> 适用版本：MaimaiHelper v2.1.55

## 1. 文档目的

本文档记录 MaimaiHelper 中 AI / ChatBot 返回内容与消费端代码之间的接口契约。代码会通过固定关键词、英文逗号、中文逗号、正则表达式或整数转换解析返回内容。

修改 AnyHelper 后台 Bot Prompt 时必须保持本文档约定的格式，否则可能造成：

- 匹配结果被错误归类；
- 候选人 UID、推荐语、薪资、居住地或优势标签提取失败；
- 聊天标签或数字状态标签无法保存；
- 自动回复内容携带模型说明并被直接发送给候选人；
- JSON 解析或整数转换异常，导致流程中断。

本文档描述的是当前代码能够识别的格式，不代表建议重新设计的格式。Bot ID 的源码位置为 [`src/config/bot.py`](../src/config/bot.py)，具体解析逻辑位于 [`src/manager.py`](../src/manager.py)。

## 2. 调用方式与 HTTP 外层响应

项目统一调用：

```text
POST https://model.example.invalid/api/completions/quora.php
Content-Type: application/x-www-form-urlencoded

prompt=<输入内容>
chatbotID=<Bot 配置标识>
```

项目源码只配置了 `chatbotID`，没有声明 GPT、Claude、DeepSeek 等底层模型名。实际模型应以 AnyHelper 后台对应 Bot 的配置为准。

HTTP 响应必须是 JSON，且至少包含：

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

固定要求：

1. `choices` 必须是非空数组。
2. 第一项必须包含 `message`。
3. `message.content` 必须是字符串。
4. 修改 Prompt 不应改变 HTTP 外层协议。

## 3. Bot 清单

| 用途 | 枚举名 | ChatBot ID |
|---|---|---|
| 二次联系消息 | `SECOND_CONTACT_MSG_GEN` | `__TALENTMATCH_MODEL_23__` |
| 自动回复 | `AUTO_REPLY_MSG_GEN` | `__TALENTMATCH_MODEL_24__` |
| 候选人文本标签 | `CANDIDATE_TAGS_GEN` | `__TALENTMATCH_MODEL_29__` |
| 简历翻译 | `RESUME_TRANSLATOR` | `__TALENTMATCH_MODEL_30__` |
| 第一次匹配 | `MATCH_CHECK_FIRST` | `__TALENTMATCH_MODEL_05__` |
| 二次事实判断 | `MATCH_CHECK_SECOND` | `__TALENTMATCH_MODEL_06__` |
| 聊天数字状态标签 | `GET_TAG_BY_CHAT_HISTORY` | `__TALENTMATCH_MODEL_22__` |
| 批量简历预筛 | `RESUME_BATCH_PRE_CHECK` | `__TALENTMATCH_MODEL_35__` |
| 筛选简历清洗 | `CLEAN_SCREENING_RESUME` | `__TALENTMATCH_MODEL_08__` |
| 简历摘要 | `AI_SUMMARY_RESUME` | `__TALENTMATCH_MODEL_19__` |
| 薪资清洗 | `GET_CLEAN_SALARY` | `__TALENTMATCH_MODEL_31__` |

## 4. 批量简历预筛

Bot：`RESUME_BATCH_PRE_CHECK`

返回通过预筛的候选人数字 UID，以英文逗号分隔：

```text
123456,234567,345678
```

固定要求：

- 每一项必须是可被 `int()` 解析的数字 UID；
- 必须使用英文逗号 `,`，不能使用中文逗号 `，`；
- 不要返回 JSON 数组、Markdown、字段名、候选人姓名或解释文字；
- 无匹配结果时返回空字符串，不要返回 `[]`、`无` 或 `没有匹配`。

禁止示例：

```text
[123456, 234567]
UID：123456,234567
123456，234567
```

## 5. 第一次匹配

Bot：`MATCH_CHECK_FIRST`

返回内容必须明确包含下列状态词之一：

```text
非常匹配
匹配
不确定
不匹配
```

推荐模板：

```text
判断结果：非常匹配，原因：候选人……
```

```text
判断结果：不匹配，原因：候选人……
```

不要将状态词替换为“符合”“合适”“建议通过”或数字评分。不要在真实结论前写容易误判的否定句，例如“并非不匹配，最终为匹配”。

## 6. 二次事实判断

Bot：`MATCH_CHECK_SECOND`

推荐固定格式：

```text
是，判断合理，确实非常匹配，原因：候选人……
```

```text
是，判断合理，确实匹配，原因：候选人……
```

```text
是，判断合理，确实不确定，原因：简历中缺少……
```

```text
否，不合理，判断结果应为不匹配，原因：候选人……
```

固定要求：

- 必须使用中文逗号 `，` 分段；不要只使用英文逗号；
- 返回中包含 `不匹配` 时，代码会判为不匹配；
- 返回中包含 `非常匹配` 时，代码会判为非常匹配；
- 上传意向人才时，包含 `不匹配` 或 `不确定` 会将状态设为 `待筛选`；
- 代码使用 `comment.split('，')` 截取原因，不能删除中文逗号结构。

## 7. 筛选简历清洗

Bot：`CLEAN_SCREENING_RESUME`

返回 Markdown，且必须包含 `**推荐语**`：

```markdown
# 候选人姓名

## 基本信息

……

## 推荐信息

**推荐语**：候选人具备……

---
```

代码使用以下正则提取推荐语，并直接调用 `.group(1)`：

```regex
\*\*推荐语\*\*[:：]?\s*([\s\S]*?)(?:\n---|\n##|$)
```

缺少 `**推荐语**` 会导致解析异常。字段名、粗体标记和冒号结构不能随意修改。

## 8. 简历摘要

Bot：`AI_SUMMARY_RESUME`

返回“简短摘要 + 三个固定 Markdown 字段”：

```markdown
候选人具备新能源出海和渠道团队管理经验。

**期待薪资**：20K-30K/月
**居住地**：上海
**优势标签**：新能源出海、渠道建设、团队管理
```

三个字段对应的解析正则为：

```regex
\*\*期待薪资\*\*[:：]?\s*(.+)
\*\*居住地\*\*[:：]?\s*(.+)
\*\*优势标签\*\*[:：]?\s*(.+)
```

不要将此 Bot 改成只有一段无字段的摘要。

## 9. 候选人文本标签

Bot：`CANDIDATE_TAGS_GEN`

允许的标签：

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

最安全的返回格式为单个 choice、单个标签：

```text
有意向沟通
```

如 HTTP 外层返回多个 choice，代码会将每个 `message.content` 用英文逗号拼接。每个 choice 都只能包含合法标签，不要返回 JSON 数组、编号列表、解释文字或集合外标签。

## 10. 聊天数字状态标签

Bot：`GET_TAG_BY_CHAT_HISTORY`

必须返回一个可被 `int()` 直接解析的纯整数：

```text
256
```

当前代码明确使用的标签包括：

| 标签 ID | 业务含义 |
|---:|---|
| `104` | 在职急寻 |
| `105` | 在职看机会 |
| `107` | 离职 |
| `109` | 需再联系 |
| `110` | 不跳槽 |
| `256` | 强意向 |

禁止返回：

```text
标签：256
256（强意向）
{"tag": 256}
```

## 11. 自动回复与二次联系

Bot：

- `AUTO_REPLY_MSG_GEN`
- `SECOND_CONTACT_MSG_GEN`

`message.content` 会作为整段消息直接发送给候选人，必须返回单条可直接发送的纯文本。

不要返回：

- “建议回复如下”等模型说明；
- 多个候选回复方案；
- JSON 或 Markdown 代码围栏；
- 思考过程或内部判断。

## 12. 简历翻译

Bot：`RESUME_TRANSLATOR`

返回 Markdown，并使用独立一行的 `---` 分隔简历区块：

```markdown
# 候选人信息

……

---

## 工作经历

……
```

代码会按 `---` 拆分内容，并在第一个区块后插入联系方式。至少保留第一个 `---`，不要改用其他分隔字符，也不要返回 JSON。

## 13. 薪资清洗

Bot：`GET_CLEAN_SALARY`

只返回一个清洗后的薪资字符串：

```text
20K-30K/月
```

不要附加字段名、说明、JSON 或多个备选结果。

## 14. Prompt 变更检查清单

更新 AnyHelper 后台 Prompt 前，逐项确认：

- Bot ID 与用途没有混用；
- HTTP 外层仍能通过 `choices[0].message.content` 读取；
- 批量预筛只返回英文逗号分隔的数字 UID；
- 第一次匹配保留标准状态词；
- 二次判断保留中文逗号结构；
- 简历清洗保留 `**推荐语**`；
- 简历摘要保留 `**期待薪资**`、`**居住地**`、`**优势标签**`；
- 文本标签只使用允许集合；
- 数字状态标签只返回纯整数；
- 自动回复与二次联系只返回一条可直接发送的纯文本；
- 简历翻译保留独立一行的 `---`；
- 薪资清洗只返回薪资值。
