const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  appendHighestEducationFields,
  extractHighestEducation,
  fetchAddScreeningResume,
  extractMaimaiEducation,
  fetchAddMaimaiScreeningResume,
} = require("../src/utils/highestEducation.js");

test("结构化多段教育选择最高学历且保持学校专业同组", () => {
  const result = extractHighestEducation([
    { School: "华东师范大学", Degree: "本科", Field: "教育学原理" },
    { School: "西班牙武康大学", Degree: "硕士", Field: "MBA" },
  ]);
  assert.deepEqual(result, { school: "西班牙武康大学", major: "MBA" });
});

test("英文结构化教育识别博士高于硕士", () => {
  const result = extractHighestEducation([
    { School: "Stanford University", Degree: "Master of Science", Field: "Computer Science" },
    { School: "MIT", Degree: "Ph.D.", Field: "Artificial Intelligence" },
  ]);
  assert.deepEqual(result, { school: "MIT", major: "Artificial Intelligence" });
});

test("脉脉原始文本选择最高学历", () => {
  const result = extractHighestEducation(
    "教育经历\n西班牙武康大学\n硕士，MBA\n2022-03至2024-03\nta有3个好友在此学校\n华东师范大学\n985\n211\n本科，教育学原理\n2009-01至2012-01\n职业标签\n人力资源管理"
  );
  assert.deepEqual(result, { school: "西班牙武康大学", major: "MBA" });
});

test("Markdown 教育段落支持学校、学历、专业分行", () => {
  const result = extractHighestEducation(
    "## 教育经历\n### 北京大学\n**学历**：硕士\n**专业**：计算机科学\n## 工作经历\n某公司"
  );
  assert.deepEqual(result, { school: "北京大学", major: "计算机科学" });
});

test("LinkedIn 教育段落支持大学名称位于学历和专业之后", () => {
  const result = extractHighestEducation(
    "## 教育经历\n**时间**：2016 - 2017\n**学历**：硕士\n**专业**：Marketing\n**大学名称**：Lancaster University\n---\n**时间**：2012 - 2016\n**学历**：本科\n**专业**：Business English\n**大学名称**：Southwestern University of Finance and Economics"
  );
  assert.deepEqual(result, {
    school: "Lancaster University",
    major: "Marketing",
  });
});

test("只有一段结构化教育且缺专业时保留学校并留空专业", () => {
  const result = extractHighestEducation([
    { university: "浙江大学", degree: "本科", field: "" },
  ]);
  assert.deepEqual(result, { school: "浙江大学", major: "" });
});

test("多段教育都没有学历时不猜测最高学历", () => {
  const result = extractHighestEducation([
    { School: "学校甲", Field: "专业甲" },
    { School: "学校乙", Field: "专业乙" },
  ]);
  assert.deepEqual(result, { school: "", major: "" });
});

test("教育段落之外出现学历词时不会把公司误判成学校", () => {
  const result = extractHighestEducation(
    "工作经历\n某科技公司\n负责硕士人才招聘\n项目经历\n校园招聘"
  );
  assert.deepEqual(result, { school: "", major: "" });
});

test("明确的单组中英文字段可以作为兜底", () => {
  assert.deepEqual(
    extractHighestEducation("School: Oxford University\nMajor: Economics"),
    { school: "Oxford University", major: "Economics" }
  );
});

test("未知、占位值和空输入保持空字段", () => {
  assert.deepEqual(
    extractHighestEducation("学校：暂无\n专业：--"),
    { school: "", major: "" }
  );
  assert.deepEqual(extractHighestEducation(null, undefined, ""), {
    school: "",
    major: "",
  });
});

test("追加字段时优先结构化来源并始终写入两个 API 字段", () => {
  const formData = new FormData();
  formData.append(
    "resume_content",
    "教育经历\n错误学校\n本科，错误专业"
  );
  const result = appendHighestEducationFields(formData, [
    { School: "正确学校", Degree: "硕士", Field: "正确专业" },
  ]);
  assert.deepEqual(result, { school: "正确学校", major: "正确专业" });
  assert.equal(formData.get("school"), "正确学校");
  assert.equal(formData.get("major"), "正确专业");
});

test("无法确定时 API 字段写入空字符串", () => {
  const formData = new FormData();
  appendHighestEducationFields(formData, "无教育信息");
  assert.equal(formData.get("school"), "");
  assert.equal(formData.get("major"), "");
});

test("上传包装器只补字段并保持原请求参数不变", async () => {
  const originalFetch = global.fetch;
  let captured;
  global.fetch = async (input, init) => {
    captured = { input, init };
    return { ok: true };
  };

  try {
    const formData = new FormData();
    formData.append("name", "张三");
    formData.append("resume_content", "学校：复旦大学\n专业：软件工程");
    const init = { method: "POST", body: formData, redirect: "follow" };
    const response = await fetchAddScreeningResume(
      "https://talent.example.invalid/api/add_screening_resume.php",
      init
    );

    assert.equal(response.ok, true);
    assert.equal(captured.input, "https://talent.example.invalid/api/add_screening_resume.php");
    assert.equal(captured.init, init);
    assert.equal(formData.get("name"), "张三");
    assert.equal(formData.get("school"), "复旦大学");
    assert.equal(formData.get("major"), "软件工程");
  } finally {
    global.fetch = originalFetch;
  }
});

test("所有新增人才入口统一补充学校专业且不触碰更新接口", () => {
  const root = path.resolve(__dirname, "..");
  const popup = fs.readFileSync(path.join(root, "src/core/popup.js"), "utf8");
  const background = fs.readFileSync(path.join(root, "src/core/background.js"), "utf8");
  const sources = `${popup}\n${background}`;
  const endpoint = "https://talent.example.invalid/api/add_screening_resume.php";

  assert.equal(sources.split(endpoint).length - 1, 33);
  assert.equal(
    (sources.match(/TalentMatchEducation\.fetchAddScreeningResume\s*\(/g) || []).length,
    23
  );
  assert.equal(
    (sources.match(/TalentMatchEducation\.fetchAddMaimaiScreeningResume\s*\(/g) || []).length,
    10
  );
  assert.doesNotMatch(
    sources,
    /(?:^|[^.\w])fetch\s*\(\s*["']https:\/\/talent\.anyhelper\.net\/api\/add_screening_resume\.php/
  );
  assert.equal(
    (sources.match(/update_screening_resume\.php/g) || []).length,
    26
  );
});

test("最高学历工具在 popup、后台和页面脚本运行环境中先于业务代码加载", () => {
  const root = path.resolve(__dirname, "..");
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json"), "utf8"));
  const popupHtml = fs.readFileSync(path.join(root, "src/ui/popup.html"), "utf8");
  const background = fs.readFileSync(path.join(root, "src/core/background.js"), "utf8");

  const isolated = manifest.content_scripts.find((item) =>
    item.matches.includes("<all_urls>") && !item.world
  );
  const maimaiMain = manifest.content_scripts.find((item) =>
    item.matches.includes("https://maimai.cn/*") && item.world === "MAIN"
  );
  const zhaopinMain = manifest.content_scripts.find((item) =>
    item.matches.includes("https://rd6.zhaopin.com/*") && item.world === "MAIN"
  );

  assert.ok(isolated.js.indexOf("src/utils/highestEducation.js") < isolated.js.indexOf("src/core/content.js"));
  assert.ok(maimaiMain.js.includes("src/utils/highestEducation.js"));
  assert.ok(zhaopinMain.js.includes("src/utils/highestEducation.js"));
  assert.ok(popupHtml.indexOf("../utils/highestEducation.js") < popupHtml.indexOf("../core/popup.js"));
  assert.match(background, /^importScripts\("\.\.\/utils\/highestEducation\.js"\);/m);
});

test("智联匹配上传在推荐语缺失时安全回退且不执行无效状态代码", () => {
  const root = path.resolve(__dirname, "..");
  const popup = fs.readFileSync(path.join(root, "src/core/popup.js"), "utf8");
  const start = popup.indexOf("// 智联招聘匹配上传");
  const end = popup.indexOf("var global_resumeInfo", start);
  const zhilianUpload = popup.slice(start, end);

  assert.ok(start >= 0 && end > start, "未找到智联匹配上传代码段");
  const dependencyInjection = zhilianUpload.indexOf("files: [HIGHEST_EDUCATION_FILE]");
  const uploadScriptInjection = zhilianUpload.indexOf("func: injectedScript");
  assert.ok(dependencyInjection >= 0, "智联上传前未显式注入最高学历工具");
  assert.ok(
    dependencyInjection < uploadScriptInjection,
    "最高学历工具必须先于智联上传主脚本注入"
  );
  assert.doesNotMatch(zhilianUpload, /^\s*s\s*$/m);
  assert.doesNotMatch(
    zhilianUpload,
    /uploadResume\.match\(recommendReg\)\[0\]/
  );
  assert.match(
    zhilianUpload,
    /recommendMatch\?\.\[0\]\?\.trim\(\)\s*\|\|\s*String\(comment\s*\|\|\s*rawComment/
  );
  assert.match(
    zhilianUpload,
    /String\(processedResume\s*\|\|\s*data\.rawResume\s*\|\|\s*""\)/
  );
  assert.match(
    zhilianUpload,
    /const educationRecords = Array\.from\(eduRows\)\.map/
  );
  assert.match(
    zhilianUpload,
    /data\.educationRecords,\s*\{ latestSchool: data\.latestSchool, latestMajor: data\.latestMajor \},\s*data\.rawResume/
  );
});

const maimaiRawResume = "教育经历\n江南大学\n本科，原始专业\n2012-09至2016-06";
const maimaiEducationCases = [
  {
    name: "原始简历缺专业时采用上传正文的完整教育记录",
    raw: "教育经历\n江南大学\n本科\n2012-09至2016-06",
    body: "教育经历\n时间：2012-09 - 2016-06\n学历：本科\n专业：计算机科学与技术\n大学名称：江南大学",
    expected: { school: "江南大学", major: "计算机科学与技术" },
  },
  {
    name: "校名与正文保持一致，不沿用原始校名",
    raw: "教育经历\n台湾崑山大學\n本科\n2011-09至2015-06",
    body: "教育经历\n学历：本科\n专业：空间设计\n大学名称：台湾崐山大学",
    expected: { school: "台湾崐山大学", major: "空间设计" },
  },
  {
    name: "IMBA 专业不会被当成下一条学历并丢失复旦大学",
    body: "## 教育经历\n\n**时间**：2015-09 - 2017-06\n**学历**：硕士\n**专业**：IMBA\n**大学名称**：复旦大学\n\n---\n\n**时间**：2005-01 - 2009-01\n**学历**：本科\n**专业**：信息管理与信息系统\n**大学名称**：中国地质大学（北京）",
    expected: { school: "复旦大学", major: "IMBA" },
  },
  {
    name: "博士缺专业时不借用后续本科专业",
    body: "教育经历\n学校：清华大学\n学历：博士\n学校：北京大学\n专业：法学\n学历：本科",
    expected: { school: "清华大学", major: "" },
  },
  {
    name: "正文缺专业时不从原始简历拼接",
    body: "教育经历\n学历：硕士\n大学名称：复旦大学",
    expected: { school: "复旦大学", major: "" },
  },
  {
    name: "仅有最高学历也保留该记录，不降级取本科字段",
    body: "教育经历\n学历：硕士\n---\n学历：本科\n学校：甲大学\n专业：数学",
    expected: { school: "", major: "" },
  },
  {
    name: "正文完全无教育信息时才整体回退到原始简历",
    body: "工作经历\n某公司\n负责硕士人才招聘",
    expected: { school: "江南大学", major: "原始专业" },
  },
  {
    name: "空教育段落不回退原始来源",
    body: "## 教育经历\n暂无\n## 工作经历\n某公司",
    expected: { school: "", major: "" },
  },
  {
    name: "占位教育字段不回退原始来源",
    body: "学校：暂无\n专业：--",
    expected: { school: "", major: "" },
  },
  {
    name: "学历均未知的多段教育不猜测",
    body: "教育经历\n学校：甲大学\n专业：数学\n---\n学校：乙大学\n专业：物理",
    expected: { school: "", major: "" },
  },
  {
    name: "同级学历按正文顺序取第一条完整记录",
    body: "教育经历\n学历：硕士\n专业：EMBA\n学校：甲大学\n时间：2008 - 2010\n学历：硕士\n专业：MBA\n学校：乙大学",
    expected: { school: "甲大学", major: "EMBA" },
  },
  {
    name: "专业和校名中的学位关键词不改变学历排序",
    body: "教育经历\nDegree: Bachelor\nMajor: MBA\nSchool: Master University\n---\nDegree: Master of Science\nMajor: Economics\nSchool: Oxford University",
    expected: { school: "Oxford University", major: "Economics" },
  },
  {
    name: "字段之间的说明行不会导致固定距离漏校",
    body: "教育经历\n学历：硕士\n专业：IMBA\n备注：在职\n研究方向：管理\n课程：战略\n成绩：优秀\n学校：复旦大学",
    expected: { school: "复旦大学", major: "IMBA" },
  },
  {
    name: "原始文本回退支持校名在前、日期在后和院校标签",
    raw: "教育经历\n西班牙武康大学\n硕士，MBA\n2022-03至2024-03\nta有3个好友在此学校\n华东师范大学\n985\n211\n本科，教育学原理\n2009-01至2012-01\n职业标签\n人力资源管理",
    body: "",
    expected: { school: "西班牙武康大学", major: "MBA" },
  },
  {
    name: "无标签的下一所学校也会截断缺失专业记录",
    body: "教育经历\n清华大学\n博士\n北京大学\n本科，法学",
    expected: { school: "清华大学", major: "" },
  },
  {
    name: "后续非教育段落不参与补全",
    body: "教育经历\n学校：复旦大学\n学历：硕士\n推荐信息\n专业：错误专业\n学校：错误学校",
    expected: { school: "复旦大学", major: "" },
  },
  {
    name: "学历与专业同行时，MBA 专业不抬高本科学历",
    body: "教育经历\n学校：甲大学\n学历：本科，MBA\n---\n学校：乙大学\n学历：硕士，经济学",
    expected: { school: "乙大学", major: "经济学" },
  },
  {
    name: "已有独立专业字段时同行专业不把学校拆到另一条记录",
    body: "教育经历\n学校：复旦大学\n专业：工商管理\n硕士，MBA",
    expected: { school: "复旦大学", major: "工商管理" },
  },
];

for (const { name, raw = maimaiRawResume, body, expected } of maimaiEducationCases) {
  test(`脉脉教育：${name}`, () => {
    assert.deepEqual(extractMaimaiEducation(raw, body), expected);
  });
}

test("脉脉教育标签排列顺序不同仍保持每条记录独立", () => {
  const orders = [
    ["school", "degree", "major"], ["school", "major", "degree"],
    ["degree", "major", "school"], ["degree", "school", "major"],
    ["major", "school", "degree"], ["major", "degree", "school"],
  ];
  for (const order of orders) {
    const records = [
      { school: "学校：清华大学", degree: "学历：博士", major: "专业：人工智能" },
      { school: "学校：北京大学", degree: "学历：本科", major: "专业：法学" },
    ];
    const body = "教育经历\n" + records.flatMap(record => order.map(key => record[key])).join("\n");
    assert.deepEqual(extractMaimaiEducation(maimaiRawResume, body), {
      school: "清华大学", major: "人工智能",
    }, order.join(","));
  }
});

test("脉脉日期与 Markdown 分隔线均阻止跨记录借用字段", () => {
  for (const boundary of ["---", "***", "___", "- - -", "时间：2012 - 2016", "2012-09至2016-06"]) {
    assert.deepEqual(extractMaimaiEducation(maimaiRawResume,
      `教育经历\n学校：清华大学\n学历：博士\n${boundary}\n专业：法学\n学历：本科\n学校：北京大学`
    ), { school: "清华大学", major: "" }, boundary);
  }
});

test("脉脉空输入安全留空，空正文仍可整体回退", () => {
  for (const empty of [null, undefined, ""]) {
    assert.deepEqual(extractMaimaiEducation(empty, empty), { school: "", major: "" });
    assert.deepEqual(extractMaimaiEducation(maimaiRawResume, empty), { school: "江南大学", major: "原始专业" });
  }
});

test("脉脉上传仅覆盖学校专业，保留正文、统一码及全部请求参数", async () => {
  const originalFetch = global.fetch;
  const response = { ok: true, text: async () => "success" };
  const request = Promise.resolve(response);
  const calls = [];
  global.fetch = (...args) => { calls.push(args); return request; };
  try {
    const body = new FormData();
    for (const [key, value] of Object.entries({
      name: "张三", source: "maimai", smart_keywords: "张_某公司_职位_原学校_原专业",
      resume_content: "教育经历\n学历：硕士\n专业：IMBA\n学校：复旦大学",
      position_id: "3646", status: "领英脉脉添加", comment: "原推荐语",
      coins_cost: "2", school: "旧学校", major: "旧专业",
    })) body.append(key, value);
    body.append("tags", "标签一");
    body.append("tags", "标签二");
    const before = [...body].filter(([key]) => key !== "school" && key !== "major");
    const init = { method: "POST", body, headers: new Headers(), redirect: "follow" };
    const input = "https://talent.example.invalid/api/add_screening_resume.php";
    assert.equal(fetchAddMaimaiScreeningResume(input, init, maimaiRawResume), request);
    assert.equal(await request, response);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], input);
    assert.equal(calls[0][1], init);
    assert.deepEqual([...body].filter(([key]) => key !== "school" && key !== "major"), before);
    assert.deepEqual(body.getAll("school"), ["复旦大学"]);
    assert.deepEqual(body.getAll("major"), ["IMBA"]);
  } finally {
    global.fetch = originalFetch;
  }
});

test("脉脉上传保持网络失败语义且不重试", async () => {
  const originalFetch = global.fetch;
  const error = new Error("offline");
  let calls = 0;
  global.fetch = () => { calls += 1; return Promise.reject(error); };
  try {
    await assert.rejects(fetchAddMaimaiScreeningResume("test", { body: new FormData() }, ""), value => value === error);
    assert.equal(calls, 1);
  } finally {
    global.fetch = originalFetch;
  }
});

test("十处脉脉新增调用接入专用入口且保留 rawResume 兜底", () => {
  const popup = fs.readFileSync(path.resolve(__dirname, "../src/core/popup.js"), "utf8");
  const buttons = [
    ["MaiMaiMappingButton", 2], ["MaiMaiFirstFilteringUpload", 2],
    ["MaiMaiUnviewedMappingButton", 1], ["MaiMaiReplyFilter", 1],
    ["MaiMaiInvestorBD", 1], ["MaiMaiUploadBD", 2], ["MaiMaiImportCompany", 1],
  ];
  for (const [button, expectedCount] of buttons) {
    const start = popup.indexOf(`document.getElementById("${button}").addEventListener`);
    const end = popup.indexOf('document.getElementById(', popup.indexOf('const button =', start) + 60);
    assert.ok(start >= 0 && end > start, button);
    const section = popup.slice(start, end);
    const calls = section.match(/TalentMatchEducation\.fetchAddMaimaiScreeningResume\([\s\S]*?profileData\.rawResume\s*\)/g) || [];
    assert.equal(calls.length, expectedCount, button);
    assert.doesNotMatch(section, /TalentMatchEducation\.fetchAddScreeningResume\s*\(/);
  }
});

test("脉脉新入口在浏览器全局环境可调用且保留通用 API", () => {
  const vm = require("node:vm");
  const source = fs.readFileSync(path.resolve(__dirname, "../src/utils/highestEducation.js"), "utf8");
  const context = { TalentMatchEducation: { existing: true } };
  vm.runInNewContext(source, context);
  assert.equal(context.TalentMatchEducation.existing, true);
  assert.equal(typeof context.TalentMatchEducation.fetchAddScreeningResume, "function");
  assert.equal(typeof context.TalentMatchEducation.fetchAddMaimaiScreeningResume, "function");
  assert.equal(context.TalentMatchEducation.extractMaimaiEducation("", "学校：复旦大学\n专业：IMBA").school, "复旦大学");
});
