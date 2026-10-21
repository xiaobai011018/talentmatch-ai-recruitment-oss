> 仓库整理说明：本文保留原模块文档与历史记录；统一运行说明见 [SETUP](../../docs/SETUP.md)，当前能力边界见 [ARCHITECTURE](../../docs/ARCHITECTURE.md)。部分历史演示数据与业务截图已从上传副本移除。

# MaimaiHelper

当前版本：`v2.1.55`

MaimaiHelper 用于脉脉候选人搜索、简历筛选、自动沟通及意向人才入库。

## 高潜人才学校与专业

一次激活新增高潜人才时，向 `add_screening_resume.php` 同时提交 `school`（学校）和 `major`（专业）。
卡片教育字段优先从本次实际提交的 `resume_content` 提取，与详情同源，不增加 AI 调用。
按最高学历选择同一段经历的学校与专业，同级学历保留源顺序。带标签的教育文本按完整记录解析，不依赖固定行距。
只有正文没有教育信息时才整组回退到原始简历；正文有教育信息但缺字段或存在歧义时保留空值，不跨来源拼接，也不做校名模糊匹配。
多段教育都无法识别学历时不猜测最高学历；最高学历记录字段为空时，不用低学历的学校或专业替换。不会自动回填历史上传记录。
日志中的“高潜教育诊断”记录解析版本、岗位/候选人 ID、字段来源、实际发送的 school/major 和 HTTP 状态，不记录整份简历、联系方式或响应正文。HTTP 200 不代表字段已正确入库，仍需核对页面。
本功能仅用于新增高潜人才，不修改意向库上传、历史人才更新、自动回复或 Excel 发起流程。
排查证据及验收要求见 [高潜教育字段排查说明](docs/high-potential-education-diagnosis.md)。

## ChatBot 配置与返回格式

项目通过 AnyHelper ChatBot 接口调用 AI。业务代码依赖固定关键词、分隔符、Markdown 字段及纯整数解析 Bot 返回内容；修改后台 Prompt 时必须保持返回格式兼容。

完整在线规范：[MaimaiHelper ChatBot 返回格式规范](./docs/chatbot-response-format.md)

### Bot 清单

| 用途 | 枚举名 | ChatBot ID | 返回格式摘要 |
|---|---|---|---|
| 批量简历预筛 | `RESUME_BATCH_PRE_CHECK` | `__TALENTMATCH_MODEL_35__` | 英文逗号分隔的数字 UID |
| 第一次匹配 | `MATCH_CHECK_FIRST` | `__TALENTMATCH_MODEL_05__` | 包含“非常匹配 / 匹配 / 不确定 / 不匹配” |
| 二次事实判断 | `MATCH_CHECK_SECOND` | `__TALENTMATCH_MODEL_06__` | 使用中文逗号分段的固定判断模板 |
| 筛选简历清洗 | `CLEAN_SCREENING_RESUME` | `__TALENTMATCH_MODEL_08__` | Markdown，必须包含 `**推荐语**` |
| 简历摘要 | `AI_SUMMARY_RESUME` | `__TALENTMATCH_MODEL_19__` | 摘要及期待薪资、居住地、优势标签 |
| 候选人文本标签 | `CANDIDATE_TAGS_GEN` | `__TALENTMATCH_MODEL_29__` | 只返回允许集合中的标签 |
| 聊天数字状态标签 | `GET_TAG_BY_CHAT_HISTORY` | `__TALENTMATCH_MODEL_22__` | 可被 `int()` 解析的纯整数 |
| 自动回复 | `AUTO_REPLY_MSG_GEN` | `__TALENTMATCH_MODEL_24__` | 单条可直接发送的纯文本 |
| 二次联系消息 | `SECOND_CONTACT_MSG_GEN` | `__TALENTMATCH_MODEL_23__` | 单条可直接发送的纯文本 |
| 简历翻译 | `RESUME_TRANSLATOR` | `__TALENTMATCH_MODEL_30__` | Markdown，以独立一行 `---` 分区 |
| 薪资清洗 | `GET_CLEAN_SALARY` | `__TALENTMATCH_MODEL_31__` | 单个清洗后的薪资字符串 |

### HTTP 外层响应

ChatBot HTTP 响应至少需要满足：

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

项目源码仅保存 `chatbotID`，不能据此确认底层使用 GPT、Claude、DeepSeek 或其他模型；实际模型以 AnyHelper 后台配置为准。

## Flask Environment Params

PYTHONUNBUFFERED=1;

FLASK_APP=main.py FLASK_ENV=development FLASK_DEBUG=1

## Explanation of Local Save File of Search Strategy
| Key | Value(e.g.) | Comment                                                                                                                                                    | Default |
| :--- | :--- |:-----------------------------------------------------------------------------------------------------------------------------------------------------------|:------------|
| **activeStatus** | `"04"` | `"01"` : 今天活跃 <br> `"02"` : 3天内活跃 <br> `"03"` : 7天内活跃 <br> `"04"` : 30天内活跃 <br> `"05"` : 最近三个月活跃 <br> `"06"` : 最近半年活跃 <br> `"07"` : 最近一年活跃                 | `""`        |
| **ageLow** / **ageHigh** | `"26"` / `"32"` | 年龄范围下限/上限                                                                                                                                                  | `""` / `""` |
| **anyKeyword** | `"0"` | `"0"` : 全部关键词 (AND) <br> `"1"` : 任意关键词 (OR)                                                                                                                | `"0"`       |
| **comPeriod** | `"0"` | `"0"` : 全部 <br> `"1"` : 目前 <br> `"2"` : 过往                                                                                                                 | `"0"`       |
| **compName** | `"上海初人信息科技有限公司"` | 当前公司名称                                                                                                                                                     | `""`        |
| **curPage** | `0` | 当前页码 (从0开始)                                                                                                                                                | `0`         |
| **eduLevels** | `["030"]` | `"040"` : 本科 <br> `"030"` : 硕士 <br> `"010"` : 博士/博士后 <br> `"050"` : 大专 <br> `"060"` : 中专/中技 <br> `"0100"` : 高中及以下                                          | `[]`        |
| **eduLevelTz** | `false` | 无用参数                                                                                                                                                       | `false`     |
| **eduLevelTzCode** | `"040"` | `"040"` : 统招本科 <br> `"030"` : 统招硕士 <br> `"010"` : 统招博士 <br> `"050"` : 统招大专                                                                                 | `""`        |
| **filterChat** | `false` | 是否过滤已沟通                                                                                                                                                    | `false`     |
| **filterDownload** | `false` | 是否过滤已下载                                                                                                                                                    | `false`     |
| **filterViewed** | `false` | 是否过滤已查看                                                                                                                                                    | `false`     |
| **graduate** | `false` | 是否应届生 (需与`workYearsLow`/`High`一致，`"0"/"1"`表示是)                                                                                                             | `""`        |
| **industryArr** | `[{"code":"H0009","name":"人工智能"}]` | 当前行业，`code` 参见 [IndustryCode.json](./resource/IndustryCode.json)                                                                                           | `[]`        |
| **jobName** | `"漏洞运营管理专家"` | 当前职位名称                                                                                                                                                     | `""`        |
| **jobPeriod** | `"0"` | `"0"` : 全部 <br> `"1"` : 目前 <br> `"2"` : 过往                                                                                                                 | `"0"`       |
| **keyword** | `"漏洞"` | 搜索关键词                                                                                                                                                      | `""`        |
| **languageContent** | `"波兰语"` | 其他语言技能（自由文本）                                                                                                                                               | `""`        |
| **languageSkills** | `["1"]` | `"1"` : 英语 <br> `"2"` : 日语 <br> `"3"` : 法语 <br> `"4"`: 普通话 <br> `"5"` : 粤语                                                                                 | `[]`        |
| **major** | `"计算机科学与技术"` | 专业                                                                                                                                                         | `""`        |
| **managerial** | `true` | 是否管理经验                                                                                                                                                     | `false`     |
| **modifytimeType** | `""` | 无用参数                                                                                                                                                       | `""`        |
| **nowCompKind** | `"020"` | `"010"` : 外商独资/外企办事处 <br> `"020"` : 中外合资(合资/合作) <br> `"030"` : 私营/民营企业 <br> `"040"` : 国有企业 <br> `"060"` : 政府机关/非盈利机构 <br> `"070"` : 事业单位 <br> `"999"` : 其他 | `""`        |
| **nowDqsOut** | `[{"dqName":"上海","dqCode":"020"}]` | 当前所在地，`dqCode` 参见 [CityCode.json](./resource/CityCode.json)                                                                                                | `[]`        |
| **nowJobTitleArr** | `[{"code":"N000015","name":"C++"}]` | 当前职位，`code` 参见 [JobTitleCode.json](./resource/JobTitleCode.json)                                                                                           | `[]`        |
| **nowSalaryLow** / **nowSalaryHigh** | `"16"` / `"20"` | 当前薪资范围下限/上限 (单位: K)                                                                                                                                        | `""` / `""` |
| **resLanguage** | `"0"` | `"0"` : 中文简历 <br> `"1"` : 英文简历                                                                                                                             | `""`        |
| **resumetype** | `"0"` | `"0"` : 精英简历 <br> `"1"` : 名片简历                                                                                                                             | `"0"`       |
| **school** | `"上海交通大学"` | 毕业院校                                                                                                                                                       | `""`        |
| **schoolKindList** | `["2"]` | `"2"` : 211 <br> `"1"` : 985 <br> `"9"` : 双一流 <br> (与`studyAbroad`无关)                                                                                      | `false`     |
| **searchType** | `"0"` | 无用参数                                                                                                                                                       | `"0"`       |
| **sex** | `"1"` | `"0"` : 女 <br> `"1"` : 男                                                                                                                                   | `""`        |
| **sortType** | `"0"` | `"0"`: 智能排序 <br> `"27"` : 活跃度排序                                                                                                                            | `"0"`       |
| **studyAbroad** | `false` | 是否海外留学 (与`schoolKindList`无关)                                                                                                                               | `false`     |
| **userHope** | `"0,3"` | `"0"` : 在职，看看新机会 <br> `"1"` : 离职，正在找工作 <br> `"2"` : 在职，急寻新工作 <br> `"3"` : 在职，暂无跳槽打算                                                                        | `""`        |
| **wantDqsOut** | `[{"dqName":"北京","dqCode":"010"}]` | 期望工作地，`dqCode` 参见 [CityCode.json](./resource/CityCode.json)                                                                                               | `[]`        |
| **wantIndustryArr** | `[{"code":"H0010","name":"物联网"}]` | 期望行业，`code` 参见 [IndustryCode.json](./resource/IndustryCode.json)                                                                                          | `[]`        |
| **wantJobTitleArr** | `[{"code":"N000018","name":"Python"}]` | 期望职位，`code` 参见 [JobTitleCode.json](./resource/JobTitleCode.json)                                                                                          | `[]`        |
| **wantSalaryLow** / **wantSalaryHigh** | `"25"` / `"36"` | 期望薪资范围下限/上限 (单位: K)                                                                                                                                        | `""` / `""` |
| **workAbroad** | `true` | 是否海外工作经历                                                                                                                                                   | `false`     |
| **workYearsLow** / **workYearsHigh** | `"5"` / `"10"` | 工作年限范围下限/上限 <br> (无可选点击项时为`自定义`，设为`"0" / "1"`表示`应届生`)                                                                                                      | `""` / `""` |
