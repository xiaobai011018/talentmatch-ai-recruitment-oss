const test = require("node:test");
const assert = require("node:assert/strict");

const {
  getClientScreeningResumeFields,
} = require("../src/utils/clientScreeningResumeFields.js");
const {
  buildH5CandidateContent,
  cleanCandidateInsight,
  extractProcessedResumeCandidateName,
  extractProcessedResumeRecommend,
  normalizeCandidateName,
} = require("../src/utils/extractProcessedResumeField.js");

const recommend = "具备大型制造业财务与成本管控经验";

test("不确定时使用待联系状态且备注显示一般匹配", () => {
  const fields = getClientScreeningResumeFields("判断结果应为不确定", recommend);

  assert.deepEqual(fields, {
    status: "待联系",
    comment: `一般匹配，${recommend}`,
  });
  assert.doesNotMatch(fields.comment, /不确定是否匹配/);
});

test("不匹配时保持一般匹配和备用人才映射", () => {
  assert.deepEqual(getClientScreeningResumeFields("判断结果为不匹配", recommend), {
    status: "备用人才",
    comment: `一般匹配，${recommend}`,
  });
});

test("非常匹配时保持非常匹配和待联系映射", () => {
  assert.deepEqual(getClientScreeningResumeFields("判断结果为非常匹配", recommend), {
    status: "待联系",
    comment: `非常匹配，${recommend}`,
  });
});

test("普通匹配时保持匹配和待联系映射", () => {
  assert.deepEqual(getClientScreeningResumeFields("判断结果为匹配", recommend), {
    status: "待联系",
    comment: `匹配，${recommend}`,
  });
});

test("姓名字段优先于模型返回的候选人占位值", () => {
  const processedResume = [
    "# 候选人姓名：候选人",
    "**推荐语**：姓名：郑** 拥有近11年人力资源与薪酬绩效经验。",
    "---",
  ].join("\n");

  assert.equal(
    extractProcessedResumeCandidateName(processedResume),
    "郑**"
  );
  assert.equal(
    extractProcessedResumeRecommend(processedResume, "郑**"),
    "拥有近11年人力资源与薪酬绩效经验。"
  );
});

test("候选人姓名为真实值时仍可正常提取", () => {
  assert.equal(
    extractProcessedResumeCandidateName("**候选人姓名**：程**\n**年龄**：35"),
    "程**"
  );
});

test("占位姓名会被拒绝", () => {
  assert.equal(normalizeCandidateName("候选人"), "");
  assert.equal(normalizeCandidateName("未提供"), "");
});

test("AI 洞察开头的姓名标签与重复姓名会被清除", () => {
  assert.equal(
    cleanCandidateInsight("姓名：郑** 非常匹配，具备薪酬体系经验。", "郑**"),
    "非常匹配，具备薪酬体系经验。"
  );
  assert.equal(
    cleanCandidateInsight("郑**，具备薪酬体系经验。", "郑**"),
    "具备薪酬体系经验。"
  );
});

test("H5 发送前从最终备注恢复真实姓名并覆盖候选人占位值", () => {
  assert.deepEqual(
    buildH5CandidateContent(
      "候选人",
      "姓名：潘** 非常匹配，拥有19年财务管理经验。"
    ),
    {
      name: "潘**",
      comment: "非常匹配，拥有19年财务管理经验。",
      content: "姓名：潘**\n匹配原因：非常匹配，拥有19年财务管理经验。",
    }
  );
});
