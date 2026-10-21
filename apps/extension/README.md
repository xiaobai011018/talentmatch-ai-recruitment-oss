> 仓库整理说明：本文保留原模块文档与历史记录；统一运行说明见 [SETUP](../../docs/SETUP.md)，当前能力边界见 [ARCHITECTURE](../../docs/ARCHITECTURE.md)。部分历史演示数据与业务截图已从上传副本移除。


# Talent Match插件教学文档
---

## 项目文档

| 文档 | 内容 |
|---|---|
| [ChatBot 返回格式与解析规范](docs/ChatBot返回格式正则文档.md) | 按 Bot ID 记录五个项目当前使用的返回格式、解析规则和变更注意事项。 |
| [LinkedIn 总结近期动态说明](docs/LinkedIn总结近期动态说明.md) | Sales Navigator 批量总结近期动态：列表弹窗优先、公开主页 Activity 兜底、侧栏只读基本信息。 |
| [TalentMatch 2.0 说明](docs/README.md) | 项目概述、平台功能、界面改进和历史重构记录。 |

修改 Chatbot Prompt、Bot 配置或消费端解析规则前，请先查阅规范，并在变更后同步更新文档。

## 插件 ChatBot 与返回格式

### 通用接口

插件中的 AnyHelper ChatBot 通常调用：

```text
POST https://model.example.invalid/api/completions/quora.php
```

调用方读取 `choices[0].message.content`，因此 HTTP 外层响应至少应为：

```json
{
  "choices": [
    {
      "message": {
        "content": "ChatBot 实际返回内容"
      }
    }
  ]
}
```

`chatbotID` 仅表示 AnyHelper 后台的 Bot 配置，不能据此确认底层模型。Bot、Prompt 或解析规则有变更时，以 [ChatBot 返回格式与解析规范](docs/ChatBot返回格式正则文档.md) 为完整契约。

### 插件使用的 Bot

| 用途 | ChatBot ID | `message.content` 返回格式 |
|---|---|---|
| 初筛/首次匹配 | `__TALENTMATCH_MODEL_05__` | 必须包含 `非常匹配`、`匹配`、`不确定` 或 `不匹配` |
| 事实判断/二次复核 | `__TALENTMATCH_MODEL_06__` | 中文逗号分隔的固定四段句式 |
| 清洗简历 | `__TALENTMATCH_MODEL_08__` | 固定字段的 Markdown |
| 格式化简历 | `__TALENTMATCH_MODEL_07__` | 固定字段的 Markdown |
| 简历摘要 | `__TALENTMATCH_MODEL_19__` | 非空纯文本 |
| 候选人列表筛选 | `__TALENTMATCH_MODEL_04__` | JSON 字符串数组 |
| 猎聘搜索关键词 | `__TALENTMATCH_MODEL_09__` | 固定三行关键词字段 |
| 随机搜索策略 | `__TALENTMATCH_MODEL_26__` | 固定三行关键词字段 |
| LinkedIn 搜索 URL | `__TALENTMATCH_MODEL_10__` | 完整 URL，建议只返回 URL |
| 策略名称 | `__TALENTMATCH_MODEL_14__` | 简短单行纯文本 |
| 策略名称 | `__TALENTMATCH_MODEL_01__` | 简短单行纯文本 |
| 公司全称提取 | `__TALENTMATCH_MODEL_17__` | 只返回公司全称 |
| BOSS 岗位要求整理 | `__TALENTMATCH_MODEL_16__` | 干净的岗位要求纯文本 |
| 岗位/公司信息整理 | `__TALENTMATCH_MODEL_18__` | 干净的岗位要求纯文本 |
| 平台专用匹配 | `__TALENTMATCH_MODEL_12__` | 使用初筛的四个固定状态词 |
| 平台专用匹配 | `__TALENTMATCH_MODEL_13__` | 使用初筛的四个固定状态词 |
| 平台专用匹配 | `__TALENTMATCH_MODEL_15__` | 使用初筛的四个固定状态词 |
| LinkedIn 公司分析 | `__TALENTMATCH_MODEL_02__` | 简短纯文本 |
| LinkedIn 公司判断 | `__TALENTMATCH_MODEL_03__` | 建议以 `是` 或 `否` 开头 |
| LinkedIn 近期动态总结 | `__TALENTMATCH_MODEL_20__` | 非空总结纯文本 |
| 选中文本分析 | `__TALENTMATCH_MODEL_21__` | 非空纯文本 |

已注释的旧 LinkedIn 搜索 URL Bot `__TALENTMATCH_MODEL_11__` 不是当前调用，不应配置为线上主 Bot。

### 关键返回模板

初筛结论必须前置，不要使用同义词或纯数字评分：

```text
判断结果：非常匹配，原因：候选人……
判断结果：匹配，原因：候选人……
判断结果：不确定，原因：简历中缺少……
判断结果：不匹配，原因：候选人……
```

事实判断必须保留中文逗号 `，` 以及四段结构：

```text
是，判断合理，确实非常匹配，原因或推荐语……
是，判断合理，确实匹配，原因或推荐语……
是，判断合理，确实不确定，缺失信息……
否，不合理，判断结果应为不匹配，原因……
```

清洗/格式化简历必须保留字段名、粗体标记、中文冒号及推荐语后的 `---`：

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

插件会按“推荐语”“期待薪资”“居住地”和“优势标签”做正则提取，不要改成“推荐理由”“薪资期望”“所在地”等同义字段。

```regex
\*\*推荐语\*\*[:：]?\s*([\s\S]*?)(?:\n---|\n##|$)
\*\*期待薪资\*\*[:：]?\s*(.+)
\*\*居住地\*\*[:：]?\s*(.+)
\*\*优势标签\*\*[:：]?\s*(.+)
```

候选人列表筛选结果会直接执行 `JSON.parse(content)`：

```json
["张三", "李四"]
```

无结果必须返回：

```json
[]
```

不要增加说明文字，也不要改成 `{"names":[]}`。

猎聘搜索关键词必须一行一个字段；行业关键词必须与插件内置行业名完全一致：

```text
简历描述关键词：会计师事务所 审计经理 CPA 团队管理
职位关键词：海外财务经理 财务总监 审计经理
行业关键词：新能源
```

允许的行业名称为：`AI/互联网/IT`、`电子/通信/半导体`、`房地产/建筑`、`金融`、`消费品`、`机械/制造`、`教育培训/科研`、`能源/化工`、`新能源`、`生物医药/医疗`、`汽车`、`交通/物流/仓储`、`贸易/进出口`、`专业服务`。不要返回多个行业或映射表之外的同义词。

随机搜索策略使用以下固定字段：

```text
简历描述关键词：光伏 储能 海外销售
职位关键词：海外销售总监 国际销售总监
公司名称关键词：新能源 科技 能源
```

LinkedIn 搜索 URL 通过 `/https?:\/\/[^\s]+/` 提取，最安全的返回是单独一条完整 URL；URL 后不要紧跟中文标点、Markdown 括号或解释文字。

策略名称应为简短单行文本，且不能包含 `/ \ : * ? " < > |` 等路径特殊字符。公司全称 Bot 只能返回公司全称；岗位整理、公司分析、动态总结和选中文本分析 Bot 均返回可直接使用的纯文本，不要包装成 HTTP 响应、JSON 或多个备选方案。

## 技术架构

### 文件结构
```
TalentMatch_NEW/
├── src/                          # 源代码目录
│   ├── core/                     # 核心功能模块
│   │   ├── D.js                  # 页面布局控制逻辑
│   │   ├── popup.js              # 弹窗主要逻辑
│   │   ├── background.js         # 后台脚本
│   │   └── content.js            # 内容脚本
│   ├── ui/                       # 用户界面相关
│   │   ├── popup.html            # 弹窗HTML
│   │   ├── intro.html            # 介绍页面HTML
│   │   └── styles.css            # 样式文件
│   └── utils/                    # 工具和辅助功能
│       ├── HH.js                 # 猎头相关工具
│       └── content.js.bak        # 备份文件
├── assets/                       # 静态资源
├── data/                         # 数据文件
├── config/                       # 配置文件
└── docs/                         # 文档
```

---
## 使用说明

### 安装步骤
1. 下载Chrome扩展文件
2. 打开Chrome扩展管理页面 (chrome://extensions/)
3. 启用开发者模式
4. 点击"加载已解压的扩展程序"
5. 选择TalentMatch_NEW文件夹

### 基本使用流程
1. 选择猎头/客户
2. 选择岗位
3. 选择策略
4. 根据需要在不同平台执行相应功能

---
## 按钮功能及工作流



### 通用功能

#### 1. 更新此岗位信息 (id = refreshCurrentData)
- **功能**: 为了避免岗位下加载的深匹要求过期，此按钮用于更新岗位深匹要求并且同时更新策略并重新填充至策略下拉框(strategyDropdown)
- **API**: 
  - `https://talent.example.invalid/api/get_ai_jd.php`
  - `https://talent.example.invalid/api/get_search_strategy.php`
- **工作流**: 点击后获取最新岗位信息，更新本地存储的岗位关键词和策略列表

#### 2. 当前岗位显示 (id = currentPosition)
- **功能**: 实时展示当前保存的岗位信息
- **后台可见**: extension inspect → application tab → Local Storage 查看当前保存的所有信息
- **显示内容**: 岗位名称、公司名称等关键信息

#### 3. 下拉框系统

##### a. 猎头下拉框 (id = headhuntersDropdown)
- **功能**: 打开插件时，自动获取最新猎头&客户信息并填充至此下拉框
- **API**: `https://talent.example.invalid/api/get_headhunters.php`
- **搜索功能**: 支持输入搜索猎头名称

##### b. 岗位下拉框 (id = positionsDropdown)
- **功能**: 用户选择猎头/客户后，自动获取此猎头/客户账号的所有岗位并填充至此下拉框
- **API**: `https://talent.example.invalid/api/get_jds.php`
- **触发条件**: 选择猎头后自动触发

##### c. 策略下拉框 (id = strategyDropdown)
- **功能**: 用户选择岗位后，自动获取此岗位的所有策略并填充至此下拉框
- **特殊标记**: 策略api若返回top_ranked=1，在策略前添加星号⭐
- **API**: 
  - `https://talent.example.invalid/api/get_search_strategy.php`
  - `https://talent.example.invalid/api/get_ai_jd.php`

#### 4. Cookie模块 (id = CookieBlock)

##### 导出Cookies (id = exportCookies)
- **功能**: 导出cookie为了保存某个网站的当前登录信息至本地
- **格式**: JSON/TXT格式保存
- **用途**: 备份登录状态，便于后续导入使用
- **API**: `https://talent.example.invalid/api/update_keyword_names.php`

##### 导入Cookies (id = importCookies)
- **功能**: 导入cookie为了登录某个网站
- **文件格式**: 支持JSON/TXT格式的cookie文件
- **用途**: 恢复之前保存的登录状态

##### 网络Cookies (id = onlineCookies) 
/*目前处于无用途但需留住的阶段*/
- **功能**: 从网络获取最新的cookie信息
- **用途**: 获取最新的登录状态信息

#### 5. 自定义岗位模块 (id = CustomJobDescribe || customDropdown)
- **功能**: 允许用户自定义岗位要求和描述
- **选项**:
  - 不使用自定义岗位信息(selected value="none")
  - 增加一个自定义岗位(selectedValue === "add")
  - 修改岗位要求(selectedValue === "edit")
- **用途**: 针对特殊岗位需求进行个性化配置

#### 6. 展开更多功能 (id = toggleButton)
- **功能**: 展开/收起更多功能模块

---

### 猎聘平台功能

#### 1. 随机筛选 (id = openPositionSessionLiepin)
- **功能**: 在猎聘平台进行随机筛选操作
- **显示条件**: 仅在猎聘相关页面显示
- **用途**: 根据当前岗位要求进行智能筛选
- **API**: `https://talent.example.invalid/api/get_ai_jd.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_26__` (随机搜索策略，固定三行关键词字段)
- **额外资料**: `data/dqcode.json`


#### 2. 打开批量页面 (id = LiepinOpenAllBatchButton)
- **功能**: 打开猎聘批量操作页面
- **用途**: 进行批量简历处理和管理，并且对所有批量打开页面自动进行匹配上传

#### 3. 初筛后批量查看 (id = LiepinBatchFirstFiltering)
- **功能**: 执行初筛后进行批量查看操作
- **工作流**: 先进行初筛，然后批量处理筛选结果
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)

#### 4. 分析简历 (id = fetchResume)
- **功能**: 分析当前页面的简历信息
- **用途**: 获取简历详细信息并进行匹配度分析
- **API**: 
  - `https://talent.example.invalid/api/add_screening_resume.php`
  - `https://talent.example.invalid/api/add_ai_posts.php`
  - `https://talent.example.invalid/api/add_data_count.php`
  - `https://talent.example.invalid/api/update_ai_status.php`
  - `https://talent.example.invalid/api/update_activity_time.php`
  - `https://talent.example.invalid/api/duplicate_screening_resume.php`
- **ChatBot_ID**:
  - `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
  - `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

#### 5. 批量保存功能

##### [所有人]匹配上传 (id = LiepinBatchSaveResumeAlternative)
- **功能**: 批量保存所有匹配的简历并上传
- **用途**: 大规模简历收集和上传人才库
- **API**: 
  -  `https://talent.example.invalid/api/add_screening_resume.php`
  -  `https://talent.example.invalid/api/add_ai_posts.php`
  -  `https://talent.example.invalid/api/add_data_count.php`
  -  `https://talent.example.invalid/api/update_ai_status.php`
  -  `https://talent.example.invalid/api/update_activity_time.php`
  -  `https://talent.example.invalid/api/duplicate_screening_resume.php`
- **ChatBot_ID**: 
  - `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
  - `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

##### 猎聘批量保存简历 (id = LiepinBatchSaveResumeOldAlternative)
- **功能**: 保存简历到本地表格，不对人才库进行上传
- **兼容性**: 保持与旧系统的兼容性
- **API**: 
  - `https://talent.example.invalid/api/add_screening_resume.php`
  - `https://talent.example.invalid/api/add_ai_posts.php`
  - `https://talent.example.invalid/api/add_data_count.php`
  - `https://talent.example.invalid/api/update_ai_status.php`
  - `https://talent.example.invalid/api/update_activity_time.php`
  - `https://talent.example.invalid/api/duplicate_screening_resume.php`
- **ChatBot_ID**: 
  - `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
  - `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

#### 6. 猎聘详情功能

##### 保存Liepin Detail (id = Liepin_Detail)
- **功能**: 保存猎聘职位详细信息
- **用途**: 保存职位描述、要求等详细信息

#### 7. 猎聘初筛功能

##### 猎聘初筛匹配上传 (id = LiepinFirstFilteringUpload)
- **功能**: 执行猎聘平台的初筛匹配上传
- **工作流**: 初筛 → 匹配 → 上传
- **API**: 
  - `https://talent.example.invalid/api/add_screening_resume.php`
  - `https://talent.example.invalid/api/add_ai_posts.php`
  - `https://talent.example.invalid/api/add_data_count.php`
  - `https://talent.example.invalid/api/update_ai_status.php`
  - `https://talent.example.invalid/api/update_activity_time.php`
  - `https://talent.example.invalid/api/duplicate_screening_resume.php`
- **ChatBot_ID**: 
  - `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
  - `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

##### 初筛Mapping (id = start)
- **功能**: 开始当前页面Mapping操作
- **用途**: 对当前页面简历进行初筛映射
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)

#### 8. 简历保存功能

##### 保存单个猎聘简历到本地 (id = LiepinSaveResume)
- **功能**: 保存单个猎聘简历到本地存储
- **格式**: 支持多种格式保存
- **用途**: 个人简历收藏和管理
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)

#### 9. 猎聘BD功能

##### 对标公司打开 (id = LiepinBatchCompanyFiltering)
- **功能**: 打开对标公司筛选功能
- **用途**: 根据公司信息进行筛选

##### 开始当前页面BD上传 (id = LiepinUploadBD)
- **功能**: 开始当前页面的BD信息上传
- **用途**: 上传商务拓展相关信息
- **ChatBot_ID**: `__TALENTMATCH_MODEL_13__` (平台专用匹配判断)

#### 10. Session管理功能

##### 打开筛选条件(Session) (id = uploadBtn)
- **功能**: 打开筛选条件Session文件
- **文件格式**: 支持JSON格式
- **用途**: 导入之前保存的筛选条件

##### 保存筛选条件Session (id = save-filter-session)
- **功能**: 保存当前的筛选条件Session
- **格式**: JSON格式保存
- **用途**: 备份当前的筛选条件
- **API**: `https://talent.example.invalid/api/add_search_strategy.php`
- **API**: `https://talent.example.invalid/api/duplicate_search_strategy.php`
- **API**: `https://talent.example.invalid/api/get_search_strategy.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_26__` (随机搜索策略，固定三行关键词字段)
---

### 脉脉平台功能

#### 1. 脉脉主要功能

##### 匹配上传 (id = MaiMaiMappingButton)
- **功能**: 执行脉脉平台的匹配上传操作
- **用途**: 上传匹配的脉脉用户信息
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

##### 未查看匹配上传 (id = MaiMaiUnviewedMappingButton)
- **功能**: 上传未查看的匹配用户信息
- **用途**: 处理未读的匹配信息
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

##### 保存策略 (id = MaiMaiSaveSession)
- **功能**: 保存脉脉平台的筛选策略
- **用途**: 保存当前的筛选条件和策略
- **API**: `https://talent.example.invalid/api/add_search_strategy.php`
- **API**: `https://talent.example.invalid/api/duplicate_search_strategy.php`
- **API**: `https://talent.example.invalid/api/get_search_strategy.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_01__` (策略名称，简短单行文本)

#### 2. 脉脉BD功能

##### 开始当前页面BD上传 (id = MaiMaiUploadBD)
- **功能**: 开始当前页面的BD信息上传
- **用途**: 上传脉脉平台的商务拓展信息
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_13__` (平台专用匹配判断)

##### 指定公司上传 (id = MaiMaiImportCompany)
- **功能**: 上传指定公司的相关信息
- **用途**: 针对特定公司进行信息收集
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_13__` (平台专用匹配判断)

#### 3. 脉脉初筛功能

##### 开始初筛和回复 (id = MaiMaiReplyFilter)
- **功能**: 执行初筛并进行回复操作
- **工作流**: 初筛 → 自动回复
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_06__` (事实判断，中文逗号固定四段格式)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

##### 脉脉初筛匹配上传 (id = MaiMaiFirstFilteringUpload)
- **功能**: 执行脉脉平台的初筛匹配上传
- **工作流**: 初筛 → 匹配 → 上传
- **API**: `http://localhost:8000/MaiMaiResumeSave/` (本地服务器)
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

---

### 领英平台功能

#### 1. 领英主要功能

##### 随机筛选 (id = openPositionSessionLinkedIn)
- **功能**: 在领英平台进行随机筛选操作
- **显示条件**: 仅在领英相关页面显示
- **用途**: 根据当前岗位要求进行智能筛选
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_10__` (LinkedIn 搜索 URL；底层模型未验证)

#### 2. 领英Mapping功能

##### LinkedInMapping跳过Viewed (id = LinkedInMappingButtonAllSkipViewed)
- **功能**: 执行领英平台的Mapping操作，跳过已查看的用户
- **用途**: 批量处理未查看的领英用户信息
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)
- **API**: `https://talent.example.invalid/api/add_screening_resume.php`
- **API**: `https://talent.example.invalid/api/add_ai_posts.php`
- **API**: `https://talent.example.invalid/api/add_data_count.php`
- **API**: `https://talent.example.invalid/api/update_ai_status.php`
- **API**: `https://talent.example.invalid/api/update_activity_time.php`
- **API**: `https://talent.example.invalid/api/duplicate_screening_resume.php`

##### 华人匹配上传 (id = LinkedInMappingButtonHuarenOnlyUpload)
- **功能**: 专门针对华人用户进行匹配上传
- **用途**: 针对华人市场的精准匹配
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)
- **API**: `https://talent.example.invalid/api/add_screening_resume.php`
- **API**: `https://talent.example.invalid/api/add_ai_posts.php`
- **API**: `https://talent.example.invalid/api/add_data_count.php`
- **API**: `https://talent.example.invalid/api/update_ai_status.php`
- **API**: `https://talent.example.invalid/api/update_activity_time.php`
- **API**: `https://talent.example.invalid/api/duplicate_screening_resume.php`

##### 未查看匹配上传 (id = LinkedInMappingButtonUnviewedUpload)
- **功能**: 上传未查看的匹配用户信息
- **用途**: 处理未读的匹配信息
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)
- **API**: `https://talent.example.invalid/api/add_screening_resume.php`
- **API**: `https://talent.example.invalid/api/add_ai_posts.php`
- **API**: `https://talent.example.invalid/api/add_data_count.php`
- **API**: `https://talent.example.invalid/api/update_ai_status.php`
- **API**: `https://talent.example.invalid/api/update_activity_time.php`
- **API**: `https://talent.example.invalid/api/duplicate_screening_resume.php`

##### [华人]Mapping (id = LinkedInMappingButton)
- **功能**: 执行华人用户的Mapping操作
- **用途**: 华人用户信息收集和映射
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

##### [所有人]Mapping (id = LinkedInMappingButtonAll)
- **功能**: 对所有用户进行Mapping操作
- **用途**: 大规模用户信息收集
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

##### [所有人]匹配上传 (id = LinkedInMappingButtonUploadAnyjob)
- **功能**: 上传所有匹配的用户信息
- **用途**: 批量上传匹配结果
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)
- **API**: `https://talent.example.invalid/api/add_screening_resume.php`
- **API**: `https://talent.example.invalid/api/add_ai_posts.php`
- **API**: `https://talent.example.invalid/api/add_data_count.php`
- **API**: `https://talent.example.invalid/api/update_ai_status.php`
- **API**: `https://talent.example.invalid/api/update_activity_time.php`
- **API**: `https://talent.example.invalid/api/duplicate_screening_resume.php`

##### [跳过Viewed-所有人]Mapping (id = LinkedInMappingButtonAllSkipViewed)
- **功能**: 跳过已查看用户，对其他用户进行Mapping
- **用途**: 避免重复处理已查看用户
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

#### 3. 领英Pipeline功能

##### Pipeline Mapping (id = LinkedInMappingButton_talent_hire)
- **功能**: 执行Pipeline的Mapping操作
- **用途**: 招聘流程中的用户信息收集
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)

##### Pipeline 匹配上传 (id = LinkedInMappingButton_talent_hire_AnyJobUpload)
- **功能**: 上传Pipeline匹配的用户信息
- **用途**: 招聘流程中的匹配结果上传
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)
- **API**: `https://talent.example.invalid/api/add_screening_resume.php`
- **API**: `https://talent.example.invalid/api/add_ai_posts.php`
- **API**: `https://talent.example.invalid/api/add_data_count.php`
- **API**: `https://talent.example.invalid/api/update_ai_status.php`
- **API**: `https://talent.example.invalid/api/update_activity_time.php`
- **API**: `https://talent.example.invalid/api/duplicate_screening_resume.php`

#### 4. 领英初筛功能

##### 初筛和回复 (id = LinkedinReplyFilter)
- **功能**: 执行初筛并进行回复操作
- **工作流**: 初筛 → 自动回复
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_14__` (策略名称，简短单行文本)

##### 领英【所有人】初筛匹配上传 (id = LinkedInFirstFilteringUpload)
- **功能**: 对所有用户执行初筛匹配上传
- **用途**: 大规模初筛操作
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)
- **API**: `https://talent.example.invalid/api/add_screening_resume.php`
- **API**: `https://talent.example.invalid/api/add_ai_posts.php`
- **API**: `https://talent.example.invalid/api/add_data_count.php`
- **API**: `https://talent.example.invalid/api/update_ai_status.php`
- **API**: `https://talent.example.invalid/api/update_activity_time.php`
- **API**: `https://talent.example.invalid/api/duplicate_screening_resume.php`

##### 领英【华人】初筛匹配上传 (id = LinkedInFirstFilteringUploadHuaren)
- **功能**: 专门针对华人用户执行初筛匹配上传
- **用途**: 华人用户的精准初筛
- **API**: `https://model.example.invalid/api/completions/quora.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_12__` (平台专用匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_07__` (格式化简历 Markdown)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_04__` (候选人列表筛选，返回 JSON 字符串数组)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_05__` (初筛/首次匹配判断)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_08__` (清洗简历 Markdown)
- **API**: `https://talent.example.invalid/api/add_screening_resume.php`
- **API**: `https://talent.example.invalid/api/add_ai_posts.php`
- **API**: `https://talent.example.invalid/api/add_data_count.php`
- **API**: `https://talent.example.invalid/api/update_ai_status.php`
- **API**: `https://talent.example.invalid/api/update_activity_time.php`
- **API**: `https://talent.example.invalid/api/duplicate_screening_resume.php`

#### 5. 领英Session功能

##### 打开筛选条件(Session) (id = uploadBtnLinkedIn)
- **功能**: 打开领英平台的筛选条件Session
- **文件格式**: 支持JSON格式
- **用途**: 导入之前保存的筛选条件

##### 保存筛选条件(Session)到本地 (id = save-filter-session-LinkedIn)
- **功能**: 保存领英平台的筛选条件到本地
- **格式**: JSON格式保存
- **用途**: 备份当前的筛选条件
- **API**: `https://talent.example.invalid/api/add_search_strategy.php`
- **API**: `https://talent.example.invalid/api/duplicate_search_strategy.php`
- **API**: `https://talent.example.invalid/api/get_search_strategy.php`
- **ChatBot_ID**: `__TALENTMATCH_MODEL_26__` (随机搜索策略，固定三行关键词字段)

#### 6. 领英详情功能

##### 企业信息收集 (id = Linkedin_Detail)
- **功能**: 收集领英平台的企业信息
- **用途**: 企业信息调研和数据收集

---

### BOSS平台功能

#### 1. BOSS详情功能

##### 保存Boss Detail (id = Boss_Detail)
- **功能**: 保存BOSS平台的职位详细信息
- **用途**: 保存职位描述、要求等详细信息

#### 2. BOSS保存功能

##### 保存岗位到本地 (id = BossSaveJD)
- **功能**: 保存BOSS平台的岗位信息到本地
- **用途**: 岗位信息收藏和管理
- **ChatBot_ID**: `__TALENTMATCH_MODEL_16__` (BOSS 岗位要求整理，返回纯文本)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_17__` (获取公司全称)

##### 保存公司所有岗位到本地 (id = BossSaveJD_Company)
- **功能**: 保存指定公司的所有岗位到本地
- **用途**: 批量保存公司岗位信息
- **ChatBot_ID**: `__TALENTMATCH_MODEL_18__` (岗位/公司信息整理，返回纯文本)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_17__` (获取公司全称)


##### 保存海外岗位到本地 (id = BossSaveJD_Overseas)
- **功能**: 保存BOSS海外岗位信息到本地
- **用途**: 海外岗位信息收集
- **ChatBot_ID**: `__TALENTMATCH_MODEL_16__` (BOSS 岗位要求整理，返回纯文本)
- **ChatBot_ID**: `__TALENTMATCH_MODEL_17__` (获取公司全称)


---

### 其他功能

#### 帮助按钮 (id = openTab)
- **功能**: 打开帮助页面或文档
- **用途**: 提供使用说明和技术支持

---


## 插件debug技巧
- 先了解每个文件的用途
  -  插件99%的功能都在`popup.js`里实现
  -  `background.js`的主要功能是实现插件的跨页面操作或者后台监视逻辑
  -  `content.js`的主要功能与`popup.js`类似，但是目前基本已经把所有功能的实现迁移至`popup.js`(以前的人没有维护`content.js`导致基本不可读，只有极少数情况会用到`content.js`)
  -  `D.js`控制的是按钮在插件里的整体布局
  -  `intro.html`是在插件里右上角问号按钮会呼出来的页面
- 其次需了解每个bot的输入与输出
  - 可通过`network tab`查看当前输入与输入，详情请看下文“debug技巧”的第二点
-  遇到bug如何解决
   -  定位哪个按钮出现的问题，通过该按钮的html id（获取按钮的html id可以通过此文档或者popup.html）在popup.js进行函数定位，所有按钮的实现函数都被```if(1){}```包裹
   -  按钮核心函数实现为```injectedScript```，了解了按钮的工作流以及日志输出后进行bug定位，随后修复
-  debug技巧
   -  日志输出在整个插件分为三个部分：
      -  网页的`console tab`
      -  extension的`console tab`
      -  `background.js` 的`service worker`, 此页面可在extension管理页面```chrome://extensions/```点击插件的`service worker`后查看
      -  根据日主输出进行问题定位
   -  不确定代码是否确切使用了api/需要查看后台以及网络资讯
      -  在同日志的三个部分，均有`network tab`，里面涵盖了代码运行的api以及网页本身的`api`，其中`header`，`payload`以及`response`会涵盖所有你需要的资讯
   -  在网页能查看某个元素，但是在console tab里无法通过代码获得？
      -  检查使用的`class`是否准确
      -  检查`iframe`是否存在，若存在，可切换至iframe进行元素的抓取，一般上元素名在iframe里不会改变(插件而言，目前只有猎聘批量查看后的页面需要切换iframe)
   -  查看插件实时存储的资料
      -  在插件的`inspect`里，`application tab`的`local storage`基本涵盖了插件当前拥有的全部资讯
      -  网页同样在`application tab`有`local storage`可查看，不过极少数情况会用到此方法进行debug

---

*Powered by Eason & Zac*
