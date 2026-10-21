const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const projectRoot = path.resolve(__dirname, "..");
const popupPath = path.join(projectRoot, "src/core/popup.js");
const popupSource = fs.readFileSync(popupPath, "utf8");

function extractNamedFunctions(source, functionName) {
  const marker = `function ${functionName}`;
  const definitions = [];
  let searchFrom = 0;

  while (true) {
    const start = source.indexOf(marker, searchFrom);
    if (start === -1) break;

    const bodyStart = source.indexOf("{", start + marker.length);
    assert.notEqual(bodyStart, -1, `${functionName} 缺少函数体`);

    let depth = 0;
    let end = bodyStart;
    for (; end < source.length; end += 1) {
      if (source[end] === "{") depth += 1;
      if (source[end] === "}") depth -= 1;
      if (depth === 0) break;
    }

    assert.ok(end < source.length, `${functionName} 函数体未闭合`);
    definitions.push(source.slice(start, end + 1));
    searchFrom = end + 1;
  }

  return definitions;
}

const helperDefinitions = extractNamedFunctions(
  popupSource,
  "buildMaimaiSmartKeywords"
);
const helpers = helperDefinitions.map(definition =>
  new Function(`${definition}; return buildMaimaiSmartKeywords;`)()
);

const behaviorCases = [
  {
    name: "中文 Markdown 标签生成五段式统一码",
    args: [
      "张三",
      "字节跳动",
      "算法工程师",
      "**学校**：北京大学\n**专业**：计算机科学",
    ],
    expected: "张_字节跳动_算法工程师_北京大学_计算机科学",
  },
  {
    name: "同一行的学校和专业可分别提取",
    args: [
      "李四",
      "腾讯",
      "产品经理",
      "学校：复旦大学 专业：软件工程",
    ],
    expected: "李_腾讯_产品经理_复旦大学_软件工程",
  },
  {
    name: "英文标签可生成五段式统一码",
    args: [
      "Alice",
      "OpenAI",
      "Researcher",
      "University: Stanford University\nMajor: Computer Science",
    ],
    expected: "A_OpenAI_Researcher_Stanford University_Computer Science",
  },
  {
    name: "缺少学校时安全降级为四段",
    args: ["王五", "百度", "研发工程师", "专业：人工智能"],
    expected: "王_百度_研发工程师_人工智能",
  },
  {
    name: "缺少专业时安全降级为四段",
    args: ["赵六", "阿里巴巴", "运营", "学校：浙江大学"],
    expected: "赵_阿里巴巴_运营_浙江大学",
  },
  {
    name: "空简历或占位值不报错并降级为三段",
    args: ["陈七", "美团", "设计师", "学校：暂无\n专业：--"],
    expected: "陈_美团_设计师",
  },
  {
    name: "无标签教育文本不做猜测",
    args: ["周八", "小米", "工程师", "教育经历：北京大学 计算机科学"],
    expected: "周_小米_工程师",
  },
  {
    name: "按脉脉真实格式选择最高学历对应的学校和专业",
    args: [
      "张先生",
      "红蜻蜓集团",
      "人力资源总监",
      "教育经历\n西班牙武康大学\n硕士，MBA\n2022-03至2024-03\nta有3个好友在此学校\n华东师范大学\n985\n211\n本科，教育学原理\n2009-01至2012-01\n职业标签\n人力资源管理",
    ],
    expected: "张_红蜻蜓集团_人力资源总监_西班牙武康大学_MBA",
  },
  {
    name: "相同最高学历按脉脉显示顺序取第一条",
    args: [
      "Sara",
      "某公司",
      "负责人",
      "教育经历\n清大经管\n硕士，工商管理（MBA）\n2023-10至2024-10\n该段经历来自附件简历\n吉林农业大学\n本科，人力资源管理\n2001-09至2005-07\n清大经管\n硕士，工商管理\n1970-01至1970-01",
    ],
    expected: "S_某公司_负责人_清大经管_工商管理（MBA）",
  },
  {
    name: "其它课程记录不高于正式学历",
    args: [
      "黄先生",
      "某科技公司",
      "总经理",
      "教育经历\n斯坦福大学\n海外Top500\n其它，Machine Learning\n2016-01至2017-01\n中国传媒大学\n211\n本科，计算机科学与技术\n2001-09至2005-07",
    ],
    expected: "黄_某科技公司_总经理_中国传媒大学_计算机科学与技术",
  },
  {
    name: "最高学历缺少专业时只保留学校",
    args: [
      "吴十",
      "某集团",
      "顾问",
      "教育经历\n某大学\n本科\n2018-09至2022-06\n职业标签\n沟通协调能力",
    ],
    expected: "吴_某集团_顾问_某大学",
  },
  {
    name: "只有其它教育记录时保持脉脉原文",
    args: [
      "Eva",
      "某公司",
      "工程师",
      "教育经历\r\nStanford University\r\n海外Top500\r\n其它, Machine Learning\r\n2016-01至2017-01",
    ],
    expected: "E_某公司_工程师_Stanford University_Machine Learning",
  },
  {
    name: "教育经历结束后的学历文字不参与选择",
    args: [
      "郑十一",
      "某公司",
      "经理",
      "教育经历\n北京工业大学\n211\n本科，计算机\n2007-09至2011-07\n职业标签\n硕士，错误内容",
    ],
    expected: "郑_某公司_经理_北京工业大学_计算机",
  },
];

test("七处注入脚本均包含相同的统一码实现", () => {
  assert.equal(helperDefinitions.length, 7);
  const normalizedDefinitions = helperDefinitions.map(definition =>
    definition.replace(/\s+/g, " ").trim()
  );
  assert.equal(new Set(normalizedDefinitions).size, 1);
});

for (const behaviorCase of behaviorCases) {
  test(behaviorCase.name, () => {
    for (const helper of helpers) {
      assert.equal(helper(...behaviorCase.args), behaviorCase.expected);
    }
  });
}

test("rawResume 为 null 或 undefined 时不报错", () => {
  for (const helper of helpers) {
    assert.equal(helper("孙九", "华为", "架构师", null), "孙_华为_架构师");
    assert.equal(
      helper("孙九", "华为", "架构师", undefined),
      "孙_华为_架构师"
    );
  }
});

test("姓名取首个 Unicode 字符且字段空白被规整", () => {
  for (const helper of helpers) {
    assert.equal(
      helper("  李 四  ", "  某   公司 ", "  高级   工程师 ", ""),
      "李_某 公司_高级 工程师"
    );
    assert.equal(helper("𠮷田", "公司", "职位", ""), "𠮷_公司_职位");
  }
});

test("统一码按 Unicode 字符安全限制在 250 字符", () => {
  for (const helper of helpers) {
    const result = helper("张三", "𠮷".repeat(300), "工程师", "");
    assert.equal(Array.from(result).length, 250);
    assert.doesNotMatch(result, /\uFFFD/);
  }
});

test("十个脉脉上传入口都使用 rawResume 生成统一码", () => {
  const calls = popupSource.match(
    /formdata\.append\("smart_keywords",\s*buildMaimaiSmartKeywords\([^;]+?profileData\.rawResume\)\);/g
  ) || [];

  assert.equal(calls.length, 10);
  for (const call of calls) assert.doesNotMatch(call, /processedResume/);
});

test("统一码不参与现有重复候选人预检查", () => {
  assert.doesNotMatch(
    popupSource,
    /duplicateCheckFormData\.append\("smart_keywords"/
  );
});

test("功能升级到 3.2.25 版本", () => {
  const manifest = JSON.parse(
    fs.readFileSync(path.join(projectRoot, "manifest.json"), "utf8")
  );
  assert.equal(manifest.version, "3.2.25");
});

test("猎聘策略未填写职位时，智联职位关键词保持为空", () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const definitions = extractNamedFunctions(
    contentSource,
    "createDefaultZhilianCondition"
  );

  assert.equal(definitions.length, 1);

  const createDefaultZhilianCondition = new Function(
    `${definitions[0]}; return createDefaultZhilianCondition;`
  )();
  const condition = createDefaultZhilianCondition();

  assert.equal(condition.jobKW, "");
  assert.notEqual(condition.jobKW, "123");
  assert.equal(condition.filteringChatted, false);
  assert.deepEqual(condition.schoolNatures, []);
});

test("猎聘当前职位“人力资源”映射为智联当前职位类型", async () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const mapperDefinition = extractNamedFunctions(
    contentSource,
    "mapLiepinJobTitlesToZhilian"
  )[0];
  const targetMapperDefinition = extractNamedFunctions(
    contentSource,
    "getLiepinMappedTargets"
  )[0];
  const mapper = new Function(
    `${targetMapperDefinition}; async ${mapperDefinition}; return mapLiepinJobTitlesToZhilian;`
  )();
  const positionMapping = JSON.parse(
    fs.readFileSync(
      path.join(projectRoot, "data/liepin_zhilian_position_map.json"),
      "utf8"
    )
  );
  const currentJobTypes = await mapper(
    [{ code: "N0038", name: "人力资源" }],
    async () => {
      throw new Error("已有编码映射时不应回退到名称查找");
    },
    positionMapping
  );
  const expectedJobTypes = await mapper([], async () => -1, positionMapping);

  assert.deepEqual(currentJobTypes, [
    { value: 2000014, label: "人力资源" },
  ]);
  assert.deepEqual(expectedJobTypes, []);
});

test("猎聘消费品、医疗健康、汽车映射为智联当前行业", () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const definition = extractNamedFunctions(
    contentSource,
    "getLiepinMappedTargets"
  )[0];
  const getLiepinMappedTargets = new Function(
    `${definition}; return getLiepinMappedTargets;`
  )();
  const industryMapping = JSON.parse(
    fs.readFileSync(
      path.join(projectRoot, "data/liepin_zhilian_industry_map.json"),
      "utf8"
    )
  );

  const currentIndustries = getLiepinMappedTargets(
    [
      { code: "H05", name: "消费品" },
      { code: "H06", name: "医疗健康" },
      { code: "H07", name: "汽车" },
    ],
    industryMapping,
    "行业"
  );

  assert.deepEqual(currentIndustries, [
    { value: 700000000, label: "批发/零售/贸易" },
    { value: 700010000, label: "快速消费品" },
    { value: 700030000, label: "耐用消费品" },
    { value: 1300000000, label: "生物医药/医疗" },
    { value: 1600000000, label: "汽车" },
  ]);
});

test("猎聘当前城市和期望城市不会反向映射", async () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const definition = extractNamedFunctions(
    contentSource,
    "mapLiepinCitiesToZhilian"
  )[0];
  const mapper = new Function(
    `async ${definition}; return mapLiepinCitiesToZhilian;`
  )();
  const cityCodes = new Map([
    ["上海", 538],
    ["北京", 530],
    ["江苏", 539],
    ["浙江", 540],
    ["广东", 548],
  ]);
  const strategy = {
    nowDqsOut: [
      { dqCode: "020", dqName: "上海" },
      { dqCode: "010", dqName: "北京" },
      { dqCode: "060", dqName: "江苏" },
      { dqCode: "070", dqName: "浙江" },
      { dqCode: "050", dqName: "广东" },
    ],
    wantDqsOut: [],
  };
  const getCode = async name => cityCodes.get(name) ?? -1;

  const currentCityIds = await mapper(strategy.nowDqsOut, getCode);
  const expectedCityIds = await mapper(strategy.wantDqsOut, getCode);

  assert.deepEqual(currentCityIds, [
    { label: "上海", value: 538 },
    { label: "北京", value: 530 },
    { label: "江苏", value: 539 },
    { label: "浙江", value: 540 },
    { label: "广东", value: 548 },
  ]);
  assert.deepEqual(expectedCityIds, []);
});

test("猎聘未要求统招时不会强制添加智联统招条件", () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const injectDefinition = extractNamedFunctions(
    contentSource,
    "inject_zhilian_strategy"
  )[0];

  assert.match(injectDefinition, /sessionObj\.eduLevelTz === true/);
  assert.doesNotMatch(injectDefinition, /!sessionObj\.eduLevelTzCode/);
});

test("猎聘到智联运行时映射字典已声明为扩展可访问资源", () => {
  const manifest = JSON.parse(
    fs.readFileSync(path.join(projectRoot, "manifest.json"), "utf8")
  );
  const resources = manifest.web_accessible_resources.flatMap(
    entry => entry.resources || []
  );

  assert.ok(resources.includes("data/liepin_zhilian_industry_map.json"));
  assert.ok(resources.includes("data/liepin_zhilian_position_map.json"));
});

test("旧猎聘策略的名称型职位仍可通过安全字典映射", () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const definition = extractNamedFunctions(
    contentSource,
    "getLiepinMappedTargets"
  )[0];
  const getLiepinMappedTargets = new Function(
    `${definition}; return getLiepinMappedTargets;`
  )();
  const positionMapping = JSON.parse(
    fs.readFileSync(
      path.join(projectRoot, "data/liepin_zhilian_position_map.json"),
      "utf8"
    )
  );

  assert.deepEqual(
    getLiepinMappedTargets(["人力资源"], positionMapping, "职位"),
    [{ value: 2000014, label: "人力资源" }]
  );
});

test("猎聘交通物流贸易零售同时覆盖智联物流和贸易", () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const definition = extractNamedFunctions(
    contentSource,
    "getLiepinMappedTargets"
  )[0];
  const getLiepinMappedTargets = new Function(
    `${definition}; return getLiepinMappedTargets;`
  )();
  const industryMapping = JSON.parse(
    fs.readFileSync(
      path.join(projectRoot, "data/liepin_zhilian_industry_map.json"),
      "utf8"
    )
  );

  assert.deepEqual(
    getLiepinMappedTargets(
      [{ code: "H13", name: "交通/物流/贸易/零售" }],
      industryMapping,
      "行业"
    ),
    [
      { value: 1000000000, label: "交通运输/仓储/物流" },
      { value: 700000000, label: "批发/零售/贸易" },
    ]
  );
});

test("猎聘年薪映射按智联月薪档向上取整并安全封顶", async () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const definition = extractNamedFunctions(contentSource, "count_salary")[0];
  const salaryDictionary = JSON.parse(
    fs.readFileSync(
      path.join(projectRoot, "data/zhilian_rd_dict_cache.json"),
      "utf8"
    )
  );
  const countSalary = new Function(
    "read_json_file",
    `async ${definition}; return count_salary;`
  )(async () => salaryDictionary);

  assert.equal((await countSalary("20"))[2], "1.7万");
  assert.equal((await countSalary("10000"))[2], "25万");
  assert.equal(await countSalary("not-a-number"), null);
});

test("未知猎聘院校类型不会向智联条件写入空值", () => {
  const contentSource = fs.readFileSync(
    path.join(projectRoot, "src/core/content.js"),
    "utf8"
  );
  const injectDefinition = extractNamedFunctions(
    contentSource,
    "inject_zhilian_strategy"
  )[0];

  assert.match(injectDefinition, /if \(map\[schoolKind\]\)/);
});
