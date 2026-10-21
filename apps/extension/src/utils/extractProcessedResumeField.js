(function initProcessedResumeFields(global) {
  /** 字段与值之间的分隔：优先标点，兜底纯空白（如 *期待薪资* 30k-50k） */
  const FIELD_SEPARATORS = [
    "\\s*[:：.。]\\s*",
    "\\s+",
  ];

  /** 单行字段默认截止：换行、分隔线 ---、或文末 */
  const DEFAULT_FIELD_UNTIL = "(?:\\n|---|$)";

  /** 无 --- 且推荐语与正文同一行时，最多取 100 字 */
  const RECOMMEND_NO_SEPARATOR_MAX_LEN = 100;

  const INVALID_CANDIDATE_NAMES = new Set([
    "",
    "候选人",
    "候选人姓名",
    "姓名",
    "未知",
    "未知候选人",
    "未提供",
    "未填写",
    "暂无",
    "无",
    "null",
    "undefined",
  ]);

  function escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  /** 构建字段标签前缀模式，兼容大模型 markdown 粗体残缺（* / ** 不对称） */
  function buildLabelPrefixPatterns(escaped, allowLoosePrefix) {
    const patterns = [
      `\\*\\*${escaped}\\*\\*`, // **label**
      `\\*${escaped}\\*`,        // *label*
      `${escaped}\\*\\*`,        // label**
      `${escaped}\\*`,           // label*
      `\\*\\*${escaped}`,        // **label（缺闭合）
      `\\*${escaped}`,           // *label（缺闭合）
    ];
    if (allowLoosePrefix) {
      patterns.push(`${escaped}.*?`, escaped);
    } else {
      patterns.push(escaped);
    }
    return patterns;
  }

  /**
   * 从 processedResume 文本中提取字段，依次尝试多种格式（markdown、纯文本、不同标点）。
   * @param {string|null|undefined} text
   * @param {string|string[]} labels
   * @param {{ until?: string, loosePrefix?: boolean, fallback?: string }} [options]
   */
  function extractProcessedResumeField(text, labels, options = {}) {
    const fallback = options.fallback ?? "";
    if (typeof text !== "string" || !text.trim()) return fallback;

    const labelList = Array.isArray(labels) ? labels : [labels];
    const until = options.until ?? DEFAULT_FIELD_UNTIL;
    const allowLoosePrefix = options.loosePrefix === true;

    for (const label of labelList) {
      const escaped = escapeRegExp(label);
      const prefixPatterns = buildLabelPrefixPatterns(escaped, allowLoosePrefix);

      for (const prefix of prefixPatterns) {
        const seps = prefix.includes("\\*") ? FIELD_SEPARATORS : [FIELD_SEPARATORS[0]];
        for (const sep of seps) {
          const regex = new RegExp(`${prefix}${sep}(.+?)(?=\\s*(?:${until}))`, "s");
          const match = text.match(regex);
          const value = match?.[1]?.trim();
          if (value) return value;
        }
      }
    }

    console.warn("[extractProcessedResumeField] 未能提取字段:", labelList.join("|"));
    return fallback;
  }

  function normalizeCandidateName(value) {
    if (typeof value !== "string") return "";
    const normalized = value
      .replace(/^[\s#>*\-•]+/, "")
      .replace(/^(?:候选人)?姓名\s*[:：.。]\s*/u, "")
      .split(/[\s,，;；|｜/]/u)[0]
      .trim();
    return INVALID_CANDIDATE_NAMES.has(normalized.toLowerCase()) ? "" : normalized;
  }

  function collectCandidateNames(text, label) {
    if (typeof text !== "string" || !text.trim()) return [];
    const escapedLabel = escapeRegExp(label);
    const linePattern = new RegExp(
      `(?:^|[\\r\\n])\\s*(?:[-#>•]\\s*)*\\*{0,2}${escapedLabel}\\*{0,2}\\s*[:：.。]\\s*([^\\r\\n]+)`,
      "gmu"
    );
    const names = [];
    for (const match of text.matchAll(linePattern)) {
      const name = normalizeCandidateName(match[1]);
      if (name) names.push(name);
    }
    if (names.length) return names;

    // 兼容“推荐语：姓名：郑** ……”这类同一行输出；前置字符不能是文字，
    // 因而不会把“候选人姓名”误识别为独立“姓名”字段。
    const inlinePattern = new RegExp(
      `(?:^|[^\\p{L}\\p{N}])\\*{0,2}${escapedLabel}\\*{0,2}\\s*[:：.。]\\s*([^\\s,，;；|｜/]+)`,
      "gmu"
    );
    for (const match of text.matchAll(inlinePattern)) {
      const name = normalizeCandidateName(match[1]);
      if (name) names.push(name);
    }
    return names;
  }

  /**
   * 姓名优先取独立“姓名”字段，再取“候选人姓名”。
   * 这样可避开模型返回“候选人姓名：候选人”后又给出“姓名：郑**”的情况。
   */
  function extractProcessedResumeCandidateName(processedResume, sourceResume = "") {
    const sources = [processedResume, sourceResume];
    for (const source of sources) {
      const directNames = collectCandidateNames(source, "姓名");
      if (directNames.length) return directNames[0];
      const candidateNames = collectCandidateNames(source, "候选人姓名");
      if (candidateNames.length) return candidateNames[0];
    }
    return "";
  }

  /**
   * 清除 AI 洞察/推荐语开头误带的“姓名：某某”，并兜底清除重复的候选人名。
   */
  function cleanCandidateInsight(value, candidateName = "") {
    if (typeof value !== "string") return "";
    let cleaned = value.trim();
    const nameLabelPrefix =
      /^(?:[-#>•]\s*)*\*{0,2}(?:候选人姓名|姓名)\*{0,2}\s*[:：.。]\s*[^\s,，;；|｜/]+\s*/u;

    while (nameLabelPrefix.test(cleaned)) {
      cleaned = cleaned.replace(nameLabelPrefix, "").trim();
    }

    const normalizedName = normalizeCandidateName(candidateName);
    if (normalizedName) {
      cleaned = cleaned
        .replace(new RegExp(`^${escapeRegExp(normalizedName)}\\s*[,，:：.。]?\\s*`, "u"), "")
        .trim();
    }
    return cleaned;
  }

  /**
   * H5 最终发送兜底：当上游姓名仍是“候选人”等占位值时，
   * 从最终备注中的“姓名：潘**”恢复真实姓名，并从洞察正文移除该字段。
   */
  function buildH5CandidateContent(candidateName, comment, sourceText = "") {
    const rawComment = typeof comment === "string" ? comment.trim() : "";
    const resolvedName =
      normalizeCandidateName(candidateName) ||
      extractProcessedResumeCandidateName(rawComment, sourceText);
    const cleanedComment = cleanCandidateInsight(rawComment, resolvedName);
    return {
      name: resolvedName,
      comment: cleanedComment,
      content: `姓名：${resolvedName}\n匹配原因：${cleanedComment}`.trim(),
    };
  }

  /**
   * 提取推荐语：
   * - 有 ---：取到 --- 前（可多行）
   * - 无 --- 且有换行：取到换行前
   * - 无 --- 且无换行：取到文末，最多 100 字
   */
  function extractProcessedResumeRecommend(text, candidateName = "") {
    if (typeof text !== "string" || !text.trim()) return "";

    let recommend = "";
    if (text.includes("---")) {
      recommend = extractProcessedResumeField(text, "推荐语", { until: "---|$" });
    } else {
      recommend = extractProcessedResumeField(text, "推荐语", { until: "\\n" });
      if (!recommend) {
        recommend = extractProcessedResumeField(text, "推荐语", { until: "$" });
        recommend = recommend.slice(0, RECOMMEND_NO_SEPARATOR_MAX_LEN);
      }
    }
    return cleanCandidateInsight(recommend, candidateName);
  }

  const api = {
    buildH5CandidateContent,
    cleanCandidateInsight,
    extractProcessedResumeCandidateName,
    extractProcessedResumeField,
    extractProcessedResumeRecommend,
    normalizeCandidateName,
  };

  Object.assign(global, api);

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
