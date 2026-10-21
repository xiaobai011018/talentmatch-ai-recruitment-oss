# BOT 严格正则 · 按钮对照与风险汇总

> 生成时间：2026-07-24  
> 范围：`src/core/popup.js`、`src/core/background.js`  
> 说明：按危险程度排序 — **严重**（抛异常中断整批）> **中等**（误判/截错）> **轻度**（空值仍上传）

## 0. 执行摘要

| 统计项 | 数量 |
|--------|------|
| popup 中 `processedResume.match` 旧正则 | **160 处** / 16 个按钮区块 |
| popup 中 `推荐语 match()[0]` 无兜底（🔴） | **31 处** |
| popup 中 `JSON.parse(keywords)` 无 try/catch（🔴） | **3 处**（猎聘批量相关） |
| popup 中事实判断双逗号 `slice`（🟠） | **21 处** |
| popup 中初筛 `includes('不匹配'|…)`（🟠） | **~179 处** |
| background 批量（`LiepinOpenAllBatchButton`） | `processedResume` **已修复**；其余 3 类仍 ⚠️ |

**最高风险按钮（🔴）**：`fetchResume`（分析简历）、猎聘/领英/脉脉/智联所有「匹配上传 / 初筛 / 批量保存」链路 — BOT 输出使用英文冒号时，**推荐语提取直接 TypeError，整批中断**。

**已部分修复**：`LiepinOpenAllBatchButton` → `background.js` 已接入 `extractProcessedResumeField.js`，不再受 popup 旧 `processedResume` 正则影响。

---

## 1. 危险等级定义

| 等级 | 含义 | 典型表现 |
|------|------|----------|
| 🔴 严重 | 抛异常中断 | `match(...)[0]`、`JSON.parse` 无兜底 → 当前候选人失败，批量可能整体停止 |
| 🟠 中等 | 逻辑/文案错误 | 初筛 `includes` 误判、事实判断逗号截断错误 → 误上传/漏上传/备注错 |
| 🟡 轻度 | 空值上传 | 用了 `?.[1]` 或 `if (match)` 判空 → 不崩溃，但 AnyJob 字段缺失 |

---

## 2. 按危险等级 · 正则模式总览

### 严重（抛异常中断）

| BOT | 严格正则/解析方式 | 代码量 | 可能导致的结果 |
|-----|------------------|--------|----------------|
| 清洗简历 Bot (cmFTU1Ro…) | `processedResume.match(recommendReg)[0]（仅认 **推荐语**： 中文冒号）` | popup.js × 31 | 推荐语字段匹配失败 → TypeError 抛异常 → 当前候选人处理中断，批量任务可能整体停止 |
| ListBot / 关键词 Bot | `JSON.parse(keywords) 无 try/catch` | popup.js × 3 | Bot 返回非合法 JSON → SyntaxError → 当前批次中断 |
| ListBot | `JSON.parse(keywords)` | background.js | JSON 非法 → 批量中断 |

### 中等（逻辑误判/字段截错）

| BOT | 严格正则/解析方式 | 代码量 | 可能导致的结果 |
|-----|------------------|--------|----------------|
| 事实判断 Bot (T2RYY04…) | `factCheckStatus/Result.slice(indexOf('，', indexOf('，')+1)+1)（依赖两个中文逗号）` | popup.js × 21 | 逗号结构不符 → comment 截错或为空 → 匹配原因/上传备注错误；confirm 弹窗文案异常 |
| 初筛 Bot (b2dPak5…) | `response/includes('不匹配'|'非常匹配'|'不确定') 子串判断` | popup.js × 179 | 措辞变化或含相反状态 → 误放行/误跳过；可能错误上传或漏上传 |
| ListBot 组装 | `初筛：…深匹 / 个人信息 分段正则` | popup.js × 98 | 分段标签缺失 → prompt 组装不完整 → 下游 Bot 输入质量下降或逻辑分支走错 |
| 事实判断 Bot | `factCheckResult.slice(双中文逗号)` | background.js | comment 截错（background 批量链路） |
| 初筛/事实判断 | `includes('不匹配') 等` | background.js | 误放行/误跳过 |

### 轻度（空值上传）

| BOT | 严格正则/解析方式 | 代码量 | 可能导致的结果 |
|-----|------------------|--------|----------------|
| 清洗简历 Bot (cmFTU1Ro…) | `processedResume.match(salaryReg/ageReg/locationReg/tagsReg)（仅认 **字段**： 中文冒号）` | popup.js × 126 | 薪资/年龄/居住地/优势标签提取为空 → 仍会上传，但 AnyJob 结构化字段缺失 |
| 格式化简历 Bot (SjBxazc5…) | `standardResume.match(/- 姓名：/) 等（固定 `- 字段：` 列表格式）` | popup.js × 43 | 姓名/当前公司/当前职位为空 → 上传时 name/company/position 缺失（用了 ?.[1] 不抛异常） |
| ListBot / 简历输出 | `/电话号码:\s*(\d+)\s*微信号:\s*(\d+)/`（固定顺序、纯数字、无分隔符变体） | popup.js × 2 | 格式不符 → phone/wechat 为空上传（不抛异常）；影响猎聘批量保存、分析简历 |
| 清洗简历 Bot | `processedResume.match(/候选人姓名：/)（仅中文冒号单行）` | popup.js × 3 | 姓名提取为空 → name 字段缺失（fetchResume 等链路） |

---

## 3. 按按钮 · 受影响功能对照表

> 仅列出 **popup 内至少命中一类未修复严格正则** 的按钮。  
> **已修复**：`LiepinOpenAllBatchButton`（background 批量）已改用 `extractProcessedResumeField.js`。

| 危险 | 按钮 ID | 界面文案 | 涉及 BOT | 严格解析点 | 可能导致的结果 |
|------|---------|----------|----------|------------|----------------|
| 🔴 | `fetchResume` | 分析简历 | 清洗简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×2)；JSON.parse(keywords)(×1)；双中文逗号截 comment(×5)；includes 初筛词(×10)；ListBot 分段正则(×16)；薪资/年龄/居住地/标签(×7)；候选人姓名：(×1)；电话/微信固定正则(×1) | 推荐语字段匹配失败 → **整批中断**；JSON 非法 → 中断；comment 截错；初筛误判；字段空值；phone/wechat 空值 |
| 🔴 | `LiepinBatchSaveResumeAlternative` | 开始保存 | 清洗简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×3)；JSON.parse(keywords)(×1)；…；电话/微信固定正则(×1) | 同上 + phone/wechat 可能为空 |
| 🔴 | `LiepinFirstFilteringUpload` | 开始初筛 | 清洗简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×1)；JSON.parse(keywords)(×1)；双中文逗号截 comment(×1)；includes 初筛词(×11)；ListBot 分段正则(×6)；薪资/年龄/居住地/标签(×7)；候选人姓名：(×1) | 推荐语匹配失败 → **中断**；JSON 非法 → 中断；comment 截错；初筛误判；字段空值 |
| 🔴 | `LinkedInMappingButtonHuarenOnlyUpload` | 华人匹配上传 | 清洗简历 + 格式化简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×3)；双中文逗号截 comment(×2)；includes 初筛词(×12)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×14)；姓名/公司/职位列表(×6) | 推荐语字段匹配失败；逗号结构不符；措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空；姓名/当前公司/当前职位为空 |
| 🔴 | `LinkedInFirstFilteringUpload` | 开始初筛 | 清洗简历 + 格式化简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×2)；双中文逗号截 comment(×2)；includes 初筛词(×12)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×14)；姓名/公司/职位列表(×6) | 推荐语字段匹配失败；逗号结构不符；措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空；姓名/当前公司/当前职位为空 |
| 🔴 | `LinkedInFirstFilteringUploadHuaren` | 开始初筛（华人） | 清洗简历 + 格式化简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×2)；双中文逗号截 comment(×2)；includes 初筛词(×12)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×14)；姓名/公司/职位列表(×6) | 推荐语字段匹配失败；逗号结构不符；措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空；姓名/当前公司/当前职位为空 |
| 🔴 | `LinkedInMappingButtonUnviewedUpload` | 未查看匹配上传 | 清洗简历 + 格式化简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×3)；双中文逗号截 comment(×2)；includes 初筛词(×12)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×14)；姓名/公司/职位列表(×6) | 推荐语字段匹配失败；逗号结构不符；措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空；姓名/当前公司/当前职位为空 |
| 🔴 | `LinkedInMappingButton_talent_hire_AnyJobUpload` | 开始保存（AnyJob 上传） | 清洗简历 + 格式化简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×3)；双中文逗号截 comment(×2)；includes 初筛词(×11)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×14)；姓名/公司/职位列表(×6) | 推荐语字段匹配失败；逗号结构不符；措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空；姓名/当前公司/当前职位为空 |
| 🔴 | `LinkedInMappingButtonUploadAnyjob` | 开始保存（AnyJob 上传） | 清洗简历 + 格式化简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×3)；双中文逗号截 comment(×2)；includes 初筛词(×12)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×14)；姓名/公司/职位列表(×6) | 推荐语字段匹配失败；逗号结构不符；措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空；姓名/当前公司/当前职位为空 |
| 🔴 | `MaiMaiFirstFilteringUpload` | 开始初筛 | 清洗简历 + 初筛 | 推荐语 `[0]`(×2)；includes 初筛词(×10) | 推荐语字段匹配失败；措辞变化或含相反状态 |
| 🔴 | `MaiMaiReplyFilter` | 脉脉 BD 发起 | 清洗简历 + 初筛 | 推荐语 `[0]`(×1)；includes 初筛词(×6) | 推荐语字段匹配失败；措辞变化或含相反状态 |
| 🔴 | `MaiMaiInvestorBD` | 脉脉投资人 BD | 清洗简历 + 初筛 | 推荐语 `[0]`(×1)；includes 初筛词(×6) | 推荐语字段匹配失败；措辞变化或含相反状态 |
| 🔴 | `MaiMaiMappingButton` | 匹配上传 | 清洗简历 + 初筛 | 推荐语 `[0]`(×2)；includes 初筛词(×10) | 推荐语字段匹配失败；措辞变化或含相反状态 |
| 🔴 | `MaiMaiImportCompany` | 指定公司上传 | 清洗简历 + 格式化简历 + 事实判断 + 初筛 + ListBot | 推荐语 `[0]`(×2)；双中文逗号截 comment(×2)；includes 初筛词(×14)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×14)；姓名/公司/职位列表(×6) | 推荐语字段匹配失败；逗号结构不符；措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空；姓名/当前公司/当前职位为空 |
| 🔴 | `ZhiLianMappingButton` | 匹配上传 | 清洗简历 + 格式化简历 + 初筛 + ListBot | 推荐语 `[0]`(×1)；includes 初筛词(×5)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×1)；姓名/公司/职位列表(×1) | 推荐语字段匹配失败；措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空；姓名/当前公司/当前职位为空 |
| 🟠 | `LiepinSaveResume` | 保存单个猎聘简历到本地 | ListBot | ListBot 分段正则(×8) | 分段标签缺失 |
| 🟠 | `LiepinBatchSaveResumeOldAlternative` | 开始保存（旧版） | ListBot | ListBot 分段正则(×8) | 分段标签缺失 |
| 🟠 | `LinkedInMappingButton_talent_hire` | 开始保存 | ListBot | ListBot 分段正则(×4) | 分段标签缺失 |
| 🟠 | `LinkedInMappingButton_talent_hire_skipViewed` | 开始去重保存 | 清洗简历 + 初筛 + ListBot | includes 初筛词(×12)；ListBot 分段正则(×4)；薪资/年龄/居住地/标签(×6) | 措辞变化或含相反状态；分段标签缺失；薪资/年龄/居住地/优势标签提取为空 |
| 🟠 | `LinkedInMappingButton` | 开始保存（默认） | ListBot | ListBot 分段正则(×4) | 分段标签缺失 |
| 🟠 | `LinkedInMappingButtonAll` | 开始保存（全部） | ListBot | ListBot 分段正则(×4) | 分段标签缺失 |
| 🟠 | `LinkedInMappingButtonAllSkipViewed` | 开始保存（跳过已查看） | ListBot | ListBot 分段正则(×4) | 分段标签缺失 |
| 🟠 | `MaiMaiUploadBD` | 开始当前页面 BD 上传 | 初筛 | includes 初筛词(×8) | 措辞变化或含相反状态 |
| 🟠 | `MaiMaiUnviewedMappingButton` | 未查看匹配上传 | 初筛 | includes 初筛词(×5) | 措辞变化或含相反状态 → 误上传/漏上传 |
| 🔴 | `LiepinOpenAllBatchButton` | 打开批量页面 | 事实判断 + 初筛 + ListBot | background：`JSON.parse(keywords)`；双中文逗号 slice；includes 初筛词 | JSON 非法 → 批量中断；comment 截错；误放行/误跳过（**processedResume 字段已修复**） |
| 🟠 | `LiepinBatchFirstFiltering` | 初筛后批量查看 | ListBot | 注入脚本内 `JSON.parse(content)`（有 try/catch） | ListBot 返回非 JSON → 跳过当页高亮；一般不中断整批 |

---

## 4. 本区块无 `processedResume` 旧正则的按钮（低风险/不同链路）

以下 popup 按钮 **click handler 内未使用** `processedResume.match`，不受「清洗简历仅中文冒号」直接影响：

| 按钮 ID | 界面文案 |
|---------|----------|
| `LinkedInMappingButton_talent_hire` | 领英 Pipeline → 开始保存 |
| `LinkedInMappingButtonAllSkipViewed` | 领英 Session → 开始保存（跳过已查看） |
| `LinkedInMappingButtonAll` | 领英 Session → 开始保存（全部） |
| `LinkedInMappingButton` | 领英 Session → 开始保存（默认） |
| `LiepinBatchSaveResumeOldAlternative` | 猎聘批量 → 开始保存（旧版） |
| `MaiMaiUnviewedMappingButton` | 脉脉 → 未查看匹配上传 |
| `MaiMaiUploadBD` | 脉脉 → 开始当前页面 BD 上传 |

> 注：上述按钮仍可能走 **初筛 includes**、**事实判断 slice**、**standardResume** 等其他严格解析（若在同 handler 或共享函数中）。

---

## 5. background 批量链路（`LiepinOpenAllBatchButton` → `background.js`）

| 项目 | 状态 | 危险 | 可能导致的结果 |
|------|------|------|----------------|
| `processedResume` 字段提取 | ✅ 已修复 | — | 已用 `extractProcessedResumeField.js` 兜底英文冒号/markdown 残缺 |
| `JSON.parse(keywords)` | ⚠️ 未修复 | 🔴 | ListBot 返回非 JSON → SyntaxError → 当前候选人/批次中断 |
| `factCheckResult.slice(双中文逗号)` | ⚠️ 未修复 | 🟠 | 上传 comment / 匹配原因截错或为空 |
| `includes('不匹配')` 等 | ⚠️ 未修复 | 🟠 | 初筛与事实判断结论不一致时误上传或误跳过 |

---

## 6. BOT Chatbot ID 速查

| 用途 | Chatbot ID | 主要严格解析 |
|------|------------|--------------|
| 初筛/首次匹配 | `__TALENTMATCH_MODEL_05__` | `includes('不匹配'|'匹配'|…)` |
| 事实判断/二次复核 | `__TALENTMATCH_MODEL_06__` | 双中文逗号 `slice` |
| 清洗简历 | `__TALENTMATCH_MODEL_08__` | `**字段**：` 仅中文冒号 |
| 格式化简历 | `__TALENTMATCH_MODEL_07__` | `- 姓名：` 列表格式 |
| ListBot 关键词 | `__TALENTMATCH_MODEL_04__` | `JSON.parse(keywords)` + 分段正则 |
| 简历摘要 | `__TALENTMATCH_MODEL_19__` | 非空纯文本（相对宽松） |

**与当前大模型标准输出的冲突**：标准格式使用英文冒号 `**期待薪资**:30k`，而 popup 旧正则要求 `**期待薪资**：`（中文冒号），是最常见的字段全空/推荐语崩溃根因。

---

## 7. 修复优先级建议（MVP）

1. **P0**：popup 全量替换 `processedResume.match` → 与 background 共用 `extractProcessedResumeField.js`（消除 🔴 推荐语 `[0]` 崩溃）
2. **P0**：`JSON.parse(keywords)` 加 try/catch + 降级（popup 猎聘批量 + background）
3. **P1**：事实判断 `slice(双中文逗号)` 改为结构化解析或正则兜底
4. **P1**：初筛 `includes` 改为锚定「判断结果：」行解析
5. **P2**：`standardResume` 列表字段改为与文档一致的多模式提取  
6. **P2**：电话/微信号正则支持空格、中文标签变体

---

## 8. 附录 A：各严格正则示例与触发条件

### 🔴 清洗简历 · 推荐语（popup 旧代码）

```javascript
const recommendReg = /(?<=\*\*推荐语\*\*：\s*).*?(?=\s*---|$)/
let recommend = processedResume.match(recommendReg)[0]  // 无兜底 → TypeError
```

**触发**：BOT 输出 `**推荐语**:…`（英文冒号）或 `*推荐语* …`（markdown 残缺）→ **整批中断**。

### 🔴 ListBot · JSON.parse(keywords)

```javascript
keywords = typeof keywords === "string" ? JSON.parse(keywords) : keywords
```

**触发**：keywords 含尾逗号、单引号、说明文字 → **SyntaxError 中断**。

### 🟠 事实判断 · 双中文逗号 slice

```javascript
factCheckComment = factCheckStatus.slice(
  factCheckStatus.indexOf("，", factCheckStatus.indexOf("，") + 1) + 1
)
```

**触发**：Bot 用英文逗号、少一个逗号、或改写句式 → comment 从错误位置截断。

### 🟠 初筛 · includes 子串

```javascript
if (!response.includes("不匹配") && factCheckComment.includes("不匹配")) { … }
let DFPassed = !comment.includes("不匹配");
```

**触发**：原因里出现「并非不匹配」、或缺少标准词但语义应通过 → **误判**。

### 🟡 格式化简历 · standardResume

```javascript
const name = standardResume.match(/- 姓名：([^\n]+)/)?.[1]
```

**触发**：Bot 输出 `# 候选人姓名：` 或 `**姓名**:` → name 为空，**不崩溃**。

### 🟡 电话/微信 · 固定格式

```javascript
const regex = /电话号码:\s*(\d+)\s*微信号:\s*(\d+)/;
```

**触发**：顺序颠倒、带 `+86`、微信号含字母 → phone/wechat 为空。

---

## 9. 附录 B：popup 各按钮 `processedResume.match` 次数

| 按钮 | match 次数 |
|------|-----------|
| 领英 Pipeline → 开始保存（AnyJob 上传） | 17 |
| 领英 Pipeline → 开始去重保存 | 6 |
| 领英 Session → 开始保存（AnyJob 上传） | 17 |
| 领英 → 未查看匹配上传 | 17 |
| 领英 → 华人匹配上传 | 17 |
| 领英 → 开始初筛 | 16 |
| 领英 → 开始初筛（华人） | 16 |
| 猎聘批量 → 开始保存 | 11 |
| 猎聘 → 开始初筛 | 9 |
| 脉脉 → 匹配上传 | 2 |
| 脉脉 → 开始初筛 | 2 |
| 脉脉 → 脉脉 BD 发起 | 1 |
| 脉脉 → 脉脉投资人 BD | 1 |
| 脉脉 → 指定公司上传 | 16 |
| 智联 → 匹配上传 | 2 |
| 猎聘 → 分析简历 | 10 |
