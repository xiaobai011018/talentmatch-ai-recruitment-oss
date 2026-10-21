# processedResume 字段提取改造汇总表

> 将 Bot 输出的 `processedResume` / `uploadResume` / `formatResume` 中推荐语、薪资、年龄、居住地、优势标签、姓名等字段，统一改为 `src/utils/extractProcessedResumeField.js` 提取；页面注入脚本前注入该工具（含 `world: "MAIN"` 场景）。

## 已改造按钮

| 平台 | 按钮 ID | 界面文案 | 状态 |
|------|---------|----------|------|
| 猎聘 | `LiepinBatchSaveResumeAlternative` | 开始保存 | ✅ 已改 |
| 猎聘 | `fetchResume` | 分析简历 | ✅ 已改 |
| 猎聘 | `LiepinFirstFilteringUpload` | 开始初筛 | ✅ 已改 |
| 猎聘 | `LiepinSaveResume` | 保存单个猎聘简历到本地 | ✅ 已改 |
| 猎聘 | `LiepinOpenAllBatchButton` | 打开批量页面 | ✅ 已改（background.js） |
| 领英 | `LinkedInMappingButton_talent_hire_AnyJobUpload` | 开始保存 | ✅ 已改 |
| 领英 | `LinkedInMappingButton_talent_hire_skipViewed` | 开始去重保存 | ✅ 已改 |
| 领英 | `LinkedInMappingButtonUploadAnyjob` | 开始保存 | ✅ 已改 |
| 领英 | `LinkedInMappingButtonUnviewedUpload` | 未查看匹配上传 | ✅ 已改 |
| 领英 | `LinkedInMappingButtonHuarenOnlyUpload` | 华人匹配上传 | ✅ 已改 |
| 领英 | `LinkedInFirstFilteringUpload` | 开始初筛 | ✅ 已改 |
| 领英 | `LinkedInFirstFilteringUploadHuaren` | 开始初筛 | ✅ 已改 |
| 领英 | `LinkedinReplyFilter` | 开始初筛 | ✅ 已改 |
| 脉脉 | `MaiMaiMappingButton` | 匹配上传 | ✅ 已改 |
| 脉脉 | `MaiMaiFirstFilteringUpload` | 开始初筛 | ✅ 已改 |
| 脉脉 | `MaiMaiUnviewedMappingButton` | 未查看匹配上传 | ✅ 已改 |
| 脉脉 | `MaiMaiUploadBD` | 开始当前页面BD上传 | ✅ 已改 |
| 脉脉 | `MaiMaiReplyFilter` | 脉脉BD发起 | ✅ 已改 |
| 脉脉 | `MaiMaiInvestorBD` | 脉脉投资人BD | ✅ 已改 |
| 脉脉 | `MaiMaiImportCompany` | 指定公司上传 | ✅ 已改 |
| 智联 | `ZhiLianMappingButton` | 匹配上传 | ✅ 已改 |

## 不涉及 processedResume 字段解析（未改，无需改）

| 平台 | 按钮 ID | 界面文案 | 状态 |
|------|---------|----------|------|
| 猎聘 | `LiepinBatchSaveResumeOldAlternative` | 开始保存 | ➖ 不涉及（发送原始简历到本地服务） |
| 领英 | `LinkedInMappingButton_talent_hire` | 开始保存 | ➖ 不涉及（发送原始简历到本地服务） |
| 领英 | `LinkedInMappingButtonAll` | 开始保存 | ➖ 不涉及（仅本地保存） |
| 领英 | `LinkedInMappingButton` | 开始保存 | ➖ 不涉及（仅本地保存） |
| 领英 | `LinkedInMappingButtonAllSkipViewed` | 开始保存 | ➖ 不涉及（仅本地保存） |
| 猎聘 | `LiepinUploadBD` | 开始当前页面BD上传 | ➖ 不涉及 |
| 猎聘 | `LiepinBatchCompanyFiltering` | 对标公司打开 | ➖ 不涉及 |
| 脉脉 | `MaiMaiSaveSession` | 保存策略 | ➖ 不涉及 |

## 改造说明

1. **字段提取**：推荐语、薪资、年龄、居住地、优势标签、姓名等，统一走 `extractProcessedResumeUploadFields` / `extractProcessedResumeRecommend` / `appendProcessedResumeFieldsToFormData`。
2. **页面注入**：`injectProcessedResumeFieldUtil` 支持 `world: "MAIN"`，脉脉/智联等 MAIN 世界脚本可正常调用工具。
3. **旧正则**：`popup.js` 中活跃的旧 `processedResume.match(recommendReg/...)` 已清零，仅剩注释里的历史代码。
4. **相关文件**：
   - `src/utils/extractProcessedResumeField.js`
   - `src/core/popup.js`
   - `src/core/background.js`
   - `src/ui/popup.html`
