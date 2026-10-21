(function initTalentMatchEducation(global) {
  "use strict";

  const EMPTY_RESULT = Object.freeze({ school: "", major: "" });
  const INVALID_VALUES = new Set([
    "",
    "-",
    "--",
    "无",
    "暂无",
    "未知",
    "未填写",
    "not found",
    "null",
    "undefined",
  ]);
  const DEGREE_RULES = [
    { rank: 7, pattern: /博士后|postdoctoral|post-doctoral/i },
    { rank: 6, pattern: /博士|ph\.?d|doctor(?:ate|al)?|dphil/i },
    { rank: 5, pattern: /硕士|研究生|master|mba|emba|m\.sc|m\.a\b/i },
    { rank: 4, pattern: /本科|学士|bachelor|b\.sc|b\.a\b/i },
    { rank: 3, pattern: /大专|专科|associate|college diploma/i },
    { rank: 2, pattern: /高中|high school/i },
    { rank: 1, pattern: /中专|技校|secondary school/i },
    { rank: 0, pattern: /其它|其他|other/i },
  ];
  const EDUCATION_START = /^(?:教育经历|教育背景|education(?:al)?(?: background| experience)?)$/i;
  const EDUCATION_STOP = /^(?:工作经历|工作经验|项目经历|职业标签|技能|更多资料|期望偏好|个人简介|资格证书|语言能力|experience|work experience|skills?|projects?)$/i;
  const NOISE_LINE = /^(?:985|211|双一流|海外Top\d+|国内Top\d+|世界Top\d+|QS(?:世界)?Top\d+|该段经历来自附件简历|ta有\d+个好友在此学校|无)$/i;
  const DATE_LINE = /^(?:(?:时间|日期|dates?)\s*[:：]\s*)?(?:\d{4}[-/.年]\d{1,2}|(?:19|20)\d{2}\s*(?:-|至|–|—))/i;

  function normalize(value) {
    return String(value ?? "").replace(/\s+/g, " ").trim();
  }

  function cleanValue(value) {
    const cleaned = normalize(value).replace(/^\*+|\*+$/g, "").trim();
    return INVALID_VALUES.has(cleaned.toLowerCase()) ? "" : cleaned;
  }

  function degreeRank(value) {
    const text = normalize(value);
    for (const rule of DEGREE_RULES) {
      if (rule.pattern.test(text)) return rule.rank;
    }
    return -1;
  }

  function valueFrom(record, keys) {
    for (const key of keys) {
      if (record && Object.prototype.hasOwnProperty.call(record, key)) {
        const value = cleanValue(record[key]);
        if (value) return value;
      }
    }
    return "";
  }

  function normalizeRecord(record) {
    if (!record || typeof record !== "object" || Array.isArray(record)) return null;
    const school = valueFrom(record, [
      "school",
      "School",
      "schoolName",
      "university",
      "University",
      "college",
      "highest_degree_school",
      "latestSchool",
    ]);
    const major = valueFrom(record, [
      "major",
      "Major",
      "field",
      "Field",
      "schoolSpecial",
      "speciality",
      "highest_degree_field",
      "latestMajor",
    ]);
    const degree = valueFrom(record, [
      "degree",
      "Degree",
      "education",
      "educationLevel",
      "highest_degree_extract",
    ]);
    if (!school && !major) return null;
    return { school, major, degree, rank: degreeRank(degree) };
  }

  function chooseHighest(records) {
    const normalized = records.map(normalizeRecord).filter(Boolean);
    if (!normalized.length) return null;

    const ranked = normalized.filter((record) => record.rank >= 0);
    if (ranked.length) {
      const highest = ranked.reduce((best, record) =>
        record.rank > best.rank ? record : best
      );
      return { school: highest.school, major: highest.major };
    }

    if (normalized.length === 1) {
      return { school: normalized[0].school, major: normalized[0].major };
    }

    return null;
  }

  function structuredRecords(source) {
    if (!source || typeof source !== "object") return [];
    if (Array.isArray(source)) return source;

    for (const key of ["Education", "education", "educations", "edu", "educationList"]) {
      if (Array.isArray(source[key])) return source[key];
    }
    if (source.eduInfoContent && typeof source.eduInfoContent === "object") {
      return [source.eduInfoContent];
    }
    return [source];
  }

  function extractTaggedPair(text) {
    const schoolPattern = /(?:\*{0,2})?(?:学校|院校|大学名称|毕业院校|毕业学校|school|university|college)(?:\*{0,2})?\s*[:：]\s*([^\n|；;]+)/gi;
    const majorPattern = /(?:\*{0,2})?(?:专业|所学专业|major|field of study)(?:\*{0,2})?\s*[:：]\s*([^\n|；;]+)/gi;
    const schools = [...text.matchAll(schoolPattern)].map((match) => cleanValue(match[1])).filter(Boolean);
    const majors = [...text.matchAll(majorPattern)].map((match) => cleanValue(match[1])).filter(Boolean);

    if (schools.length <= 1 && majors.length <= 1 && (schools.length || majors.length)) {
      return { school: schools[0] || "", major: majors[0] || "" };
    }
    return null;
  }

  function stripLineMarkup(line) {
    return normalize(line)
      .replace(/^[-#>*•]+\s*/, "")
      .replace(/\*/g, "")
      .trim();
  }

  function extractTextRecords(text) {
    const lines = String(text || "")
      .split(/\r?\n/)
      .map(stripLineMarkup)
      .filter(Boolean);
    const start = lines.findIndex((line) => EDUCATION_START.test(line));
    if (start < 0) return [];
    const scoped = lines.slice(start + 1);
    const records = [];

    for (let i = 0; i < scoped.length; i += 1) {
      const line = scoped[i];
      if (EDUCATION_STOP.test(line)) break;

      const labeledDegree = line.match(/^(?:学历|学位|degree)\s*[:：]\s*(.+)$/i);
      const degreeText = labeledDegree?.[1] || line;
      const rank = degreeRank(degreeText);
      if (rank < 0) continue;

      let major = "";
      const degreeMajor = degreeText.match(
        /(?:博士后|博士|硕士|研究生|本科|学士|大专|专科|高中|中专|其它|其他|ph\.?d|doctor(?:ate|al)?|dphil|master|mba|emba|bachelor|associate)(?:\s*[，,、]\s*(.*))?$/i
      );
      if (degreeMajor?.[1]) major = cleanValue(degreeMajor[1]);

      for (let j = i + 1; !major && j < Math.min(scoped.length, i + 3); j += 1) {
        const majorMatch = scoped[j].match(/^(?:专业|所学专业|major|field of study)\s*[:：]\s*(.+)$/i);
        if (majorMatch) major = cleanValue(majorMatch[1]);
      }

      let school = "";
      for (let j = i - 1; j >= Math.max(0, i - 4); j -= 1) {
        const candidate = scoped[j];
        const schoolMatch = candidate.match(/^(?:学校|院校|大学名称|毕业院校|毕业学校|school|university|college)\s*[:：]\s*(.+)$/i);
        if (schoolMatch) {
          school = cleanValue(schoolMatch[1]);
          break;
        }
        if (DATE_LINE.test(candidate)) break;
        if (
          degreeRank(candidate) >= 0 ||
          NOISE_LINE.test(candidate) ||
          /^(?:专业|所学专业|major|field of study)\s*[:：]/i.test(candidate)
        ) {
          continue;
        }
        school = cleanValue(candidate);
        break;
      }

      for (let j = i + 1; !school && j < Math.min(scoped.length, i + 5); j += 1) {
        const candidate = scoped[j];
        if (EDUCATION_STOP.test(candidate) || DATE_LINE.test(candidate) || degreeRank(candidate) >= 0) {
          break;
        }
        const schoolMatch = candidate.match(
          /^(?:学校|院校|大学名称|毕业院校|毕业学校|school|university|college)\s*[:：]\s*(.+)$/i
        );
        if (schoolMatch) {
          school = cleanValue(schoolMatch[1]);
        }
      }

      if (school || major) records.push({ school, major, degree: degreeText });
    }
    return records;
  }

  function extractFromString(source) {
    const text = String(source || "").trim();
    if (!text) return null;

    if (/^[\[{]/.test(text)) {
      try {
        const parsed = JSON.parse(text);
        const structured = chooseHighest(structuredRecords(parsed));
        if (structured) return structured;
      } catch (_) {
        // The text can be a normal resume beginning with a bracket.
      }
    }

    const records = extractTextRecords(text);
    const highest = chooseHighest(records);
    if (highest) return highest;
    return extractTaggedPair(text);
  }

  function extractHighestEducation(...sources) {
    for (const source of sources) {
      if (!source) continue;
      const result =
        typeof source === "string"
          ? extractFromString(source)
          : chooseHighest(structuredRecords(source));
      if (result && (result.school || result.major)) return result;
    }
    return { ...EMPTY_RESULT };
  }

  function appendHighestEducationFields(formData, ...sources) {
    if (!formData || typeof formData.append !== "function") {
      return { ...EMPTY_RESULT };
    }
    const resumeContent =
      typeof formData.get === "function" ? formData.get("resume_content") : "";
    const result = extractHighestEducation(...sources, resumeContent);
    if (typeof formData.set === "function") {
      formData.set("school", result.school);
      formData.set("major", result.major);
    } else {
      formData.append("school", result.school);
      formData.append("major", result.major);
    }
    return result;
  }

  function fetchAddScreeningResume(input, init, ...sources) {
    appendHighestEducationFields(init?.body, ...sources);
    return global.fetch(input, init);
  }

  // Maimai upload fields must describe the uploaded text. Keep the legacy
  // source priority and parser above unchanged for all other platforms.
  const MAIMAI_FIELDS = [
    ["school", /^(?:学校|院校|大学名称|毕业院校|毕业学校|school|university|college)\s*[:：]\s*(.*)$/i],
    ["major", /^(?:专业|所学专业|major|field of study)\s*[:：]\s*(.*)$/i],
    ["degree", /^(?:学历|学位|degree)\s*[:：]\s*(.*)$/i],
  ];
  const MAIMAI_DEGREE_LINE = /^(?:博士后|博士|硕士|研究生|本科|学士|大专|专科|高中|中专|技校|其它|其他|post-?doctoral|ph\.?d\.?|doctor(?:ate|al)?|dphil|master(?: of [^，,]+)?|[ei]?mba|m\.sc\.?|m\.a\.?|bachelor(?: of [^，,]+)?|b\.sc\.?|b\.a\.?|associate|college diploma|high school|secondary school|other)(?:\s*[，,、]\s*(.*))?$/i;

  function maimaiTextRecords(source) {
    if (typeof source !== "string") return { records: [], hasEducation: false };
    // Layout blanks are not record boundaries; Markdown rules are.
    const lines = source.split(/\r?\n/).filter((line) => line.trim()).map((line) =>
      /^(?:\s*[-*_]){3,}\s*$/.test(line) ? "" : stripLineMarkup(line)
    );
    const start = lines.findIndex((line) => EDUCATION_START.test(line.replace(/[:：]$/, "")));
    let hasEducation = start >= 0;
    const records = [];
    let current = {};
    function flush() {
      if (Object.keys(current).length) records.push(current);
      current = {};
    }
    function setField(key, value) {
      // Repeated fields start another record, even if the prior value is empty.
      if (Object.prototype.hasOwnProperty.call(current, key)) flush();
      const degree = key === "degree" && value.match(MAIMAI_DEGREE_LINE);
      current[key] = cleanValue(degree ? value.split(/[，,、]/)[0] : value);
      if (degree?.[1] && !Object.prototype.hasOwnProperty.call(current, "major")) {
        current.major = cleanValue(degree[1]);
      }
    }

    for (let i = start + 1; i < lines.length; i += 1) {
      const line = lines[i];
      const heading = line.replace(/[:：]$/, "");
      if (EDUCATION_STOP.test(heading) || /^(?:推荐信息|推荐语|个人信息|基本信息)$/.test(heading)) break;
      if (!line || DATE_LINE.test(line) || EDUCATION_START.test(heading)) {
        flush();
        continue;
      }
      if (NOISE_LINE.test(line)) continue;

      // Labels take precedence over degree words inside a school or major.
      const field = MAIMAI_FIELDS.find(([, pattern]) => pattern.test(line));
      if (field) {
        hasEducation = true;
        setField(field[0], line.match(field[1])[1]);
        continue;
      }
      // Only infer unlabelled fields within an explicit education section.
      if (start < 0) continue;
      if (MAIMAI_DEGREE_LINE.test(line)) {
        setField("degree", line);
        continue;
      }
      if (/[:：]/.test(line)) continue;
      let next = i + 1;
      while (next < lines.length && NOISE_LINE.test(lines[next])) next += 1;
      if (/大学|大學|学院|學院|学校|學校|\b(?:university|college|school|institute)\b/i.test(line) ||
          (next < lines.length && (MAIMAI_DEGREE_LINE.test(lines[next]) || MAIMAI_FIELDS[2][1].test(lines[next])))) {
        setField("school", line);
      }
    }
    flush();
    return { records, hasEducation };
  }

  function extractMaimaiEducation(rawResume, uploadedResume) {
    const uploaded = maimaiTextRecords(uploadedResume);
    // Fallback is whole-record only, and only when the body has no education.
    const { records } = uploaded.hasEducation ? uploaded : maimaiTextRecords(rawResume);
    const ranked = records.filter((record) => degreeRank(record.degree) >= 0);
    const highest = ranked.length
      ? ranked.reduce((best, record) => degreeRank(record.degree) > degreeRank(best.degree) ? record : best)
      : records.length === 1 ? records[0] : null;
    // Degree-only records must remain eligible: do not silently select a lower degree.
    return { school: highest?.school || "", major: highest?.major || "" };
  }

  function fetchAddMaimaiScreeningResume(input, init, rawResume) {
    const formData = init?.body;
    if (formData && typeof formData.append === "function") {
      const resumeContent = typeof formData.get === "function" ? formData.get("resume_content") : "";
      const result = extractMaimaiEducation(rawResume, resumeContent);
      for (const key of ["school", "major"]) {
        if (typeof formData.set === "function") formData.set(key, result[key]);
        else formData.append(key, result[key]);
      }
    }
    return global.fetch(input, init);
  }

  const api = {
    appendHighestEducationFields,
    extractHighestEducation,
    fetchAddScreeningResume,
    extractMaimaiEducation,
    fetchAddMaimaiScreeningResume,
  };
  global.TalentMatchEducation = Object.assign(
    global.TalentMatchEducation || {},
    api
  );

  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
