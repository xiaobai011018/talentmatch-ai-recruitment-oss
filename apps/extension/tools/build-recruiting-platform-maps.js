const fs = require("node:fs");
const path = require("node:path");
const https = require("node:https");

const projectRoot = path.resolve(__dirname, "..");
const dataDir = path.join(projectRoot, "data");

const sources = {
  industry:
    "https://bdfe.liepin.com/data/industry/V2/20231001/20251114/0.js",
  position:
    "https://bdfe.liepin.com/data/jobtitle/V2/1/20260126/20260202/0.js",
};

const industryOverrides = {
  H01: [100030000, 100040000, 100050000],
  H0001: [100120000],
  H02: [100010000, 100090000, 100140000],
  H03: [400000000],
  H04: [300000000],
  H08: [500000000],
  H0060: [500000000],
  H09: [1200000000],
  H14: [1100000000, 1100060000],
  H0039: [700050000, 700060000],
  H05: [700000000, 700010000, 700030000],
  H0072: [700120000],
  H06: [1300000000],
  H0052: [500210000],
  H0056: [1600020000],
  H07: [1600000000],
  H13: [1000000000, 700000000],
  H0106: [1000020000],
  H0108: [700000000],
  H0114: [1100050000],
  H0120: [600000000],
  H10: [800000000],
  H11: [900000000],
  H12: [1500000000],
  H0118: [1400000000],
  H0119: [1400000000],
};

// 对无法通过名称和父级自动消歧的职位，在这里维护人工映射。
// 格式：猎聘职位 code -> 智联职位 value 数组。
const positionOverrides = {};

function download(url) {
  return new Promise((resolve, reject) => {
    https
      .get(url, response => {
        if (
          response.statusCode >= 300 &&
          response.statusCode < 400 &&
          response.headers.location
        ) {
          response.resume();
          download(new URL(response.headers.location, url).href).then(
            resolve,
            reject
          );
          return;
        }
        if (response.statusCode !== 200) {
          reject(new Error(`${url} returned HTTP ${response.statusCode}`));
          response.resume();
          return;
        }
        const chunks = [];
        response.on("data", chunk => chunks.push(chunk));
        response.on("end", () =>
          resolve(Buffer.concat(chunks).toString("utf8"))
        );
      })
      .on("error", reject);
  });
}

function parseAssignedJson(source, open, close) {
  const start = source.indexOf(open);
  const end = source.lastIndexOf(close);
  if (start === -1 || end < start) {
    throw new Error("Unable to locate dictionary JSON");
  }
  return JSON.parse(source.slice(start, end + 1));
}

function flattenZhilian(items, parents = []) {
  const flattened = [];
  for (const item of items || []) {
    const pathItems = [...parents, { value: item.value, label: item.label }];
    flattened.push({
      value: item.value,
      label: item.label,
      path: pathItems.map(part => part.label),
    });
    if (Array.isArray(item.children)) {
      flattened.push(...flattenZhilian(item.children, pathItems));
    }
  }
  return flattened;
}

function normalizeLabel(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[（）]/g, character => (character === "（" ? "(" : ")"))
    .replace(/[·•]/g, "")
    .replace(/\s+/g, "")
    .replace(/／/g, "/")
    .trim();
}

function groupByLabel(items) {
  const grouped = new Map();
  for (const item of items) {
    const key = normalizeLabel(item.label);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  }
  return grouped;
}

function getLiepinAncestors(item, liepinItemsByCode) {
  const ancestors = [];
  const visited = new Set([item.code]);
  let parentCode = item.parentCode;
  while (parentCode && !visited.has(parentCode)) {
    visited.add(parentCode);
    const parent = liepinItemsByCode.get(parentCode);
    if (!parent) break;
    ancestors.unshift(parent.chName);
    parentCode = parent.parentCode;
  }
  return ancestors;
}

function toTarget(item) {
  return {
    value: item.value,
    label: item.label,
    path: item.path,
  };
}

function mapByName(liepinItem, liepinItemsByCode, zhilianByLabel) {
  const candidates =
    zhilianByLabel.get(normalizeLabel(liepinItem.chName)) || [];
  if (candidates.length === 0) {
    return { status: "unmapped", targets: [] };
  }
  if (candidates.length === 1) {
    return { status: "exact_unique", targets: [toTarget(candidates[0])] };
  }

  const ancestorLabels = new Set(
    getLiepinAncestors(liepinItem, liepinItemsByCode).map(normalizeLabel)
  );
  const scored = candidates.map(candidate => ({
    candidate,
    score: candidate.path
      .slice(0, -1)
      .map(normalizeLabel)
      .filter(label => ancestorLabels.has(label)).length,
  }));
  const maxScore = Math.max(...scored.map(item => item.score));
  const winners = scored.filter(item => item.score === maxScore);
  if (maxScore > 0 && winners.length === 1) {
    return {
      status: "exact_parent",
      targets: [toTarget(winners[0].candidate)],
    };
  }
  return {
    status: "ambiguous",
    targets: [],
    candidates: candidates.map(toTarget),
  };
}

function resolveIndustryOverride(values, zhilianByValue) {
  return values
    .map(value => zhilianByValue.get(String(value)))
    .filter(Boolean)
    .map(toTarget);
}

function summarize(mappings) {
  const summary = {};
  for (const mapping of Object.values(mappings)) {
    summary[mapping.status] = (summary[mapping.status] || 0) + 1;
  }
  return summary;
}

function writeJson(filename, value) {
  fs.writeFileSync(
    path.join(dataDir, filename),
    `${JSON.stringify(value, null, 2)}\n`,
    "utf8"
  );
}

async function main() {
  const [industrySource, positionSource] = await Promise.all([
    download(sources.industry),
    download(sources.position),
  ]);
  const liepinIndustries = parseAssignedJson(industrySource, "[", "]");
  const liepinPositionData = parseAssignedJson(positionSource, "{", "}");
  const liepinPositions = Object.values(liepinPositionData.list).filter(
    item => item && item.code && item.chName
  );

  const zhilianIndustryData = JSON.parse(
    fs.readFileSync(path.join(dataDir, "zhilian_industry_code.json"), "utf8")
  );
  const zhilianPositionData = JSON.parse(
    fs.readFileSync(path.join(dataDir, "zhilian_position_code.json"), "utf8")
  );
  const zhilianIndustries = flattenZhilian(zhilianIndustryData.data);
  const zhilianPositions = flattenZhilian(zhilianPositionData.data);
  const zhilianIndustriesByLabel = groupByLabel(zhilianIndustries);
  const zhilianPositionsByLabel = groupByLabel(zhilianPositions);
  const zhilianIndustriesByValue = new Map(
    zhilianIndustries.map(item => [String(item.value), item])
  );
  const liepinIndustriesByCode = new Map(
    liepinIndustries.map(item => [item.code, item])
  );
  const liepinPositionsByCode = new Map(
    liepinPositions.map(item => [item.code, item])
  );

  const positionMappings = {};
  for (const item of liepinPositions) {
    const override = positionOverrides[item.code];
    positionMappings[item.code] = {
      sourceName: item.chName,
      sourceParentCode: item.parentCode || "",
      ...(override
        ? {
            status: "manual_override",
            targets: override
              .map(value =>
                zhilianPositions.find(
                  candidate => String(candidate.value) === String(value)
                )
              )
              .filter(Boolean)
              .map(toTarget),
          }
        : mapByName(item, liepinPositionsByCode, zhilianPositionsByLabel)),
    };
  }

  const industryMappings = {};
  for (const item of liepinIndustries) {
    const override = industryOverrides[item.code];
    const mapped = override
      ? {
          status: "manual_override",
          targets: resolveIndustryOverride(
            override,
            zhilianIndustriesByValue
          ),
        }
      : mapByName(item, liepinIndustriesByCode, zhilianIndustriesByLabel);
    industryMappings[item.code] = {
      sourceName: item.chName,
      sourceParentCode: item.parentCode || "",
      ...mapped,
    };
  }

  writeJson("liepin_industry_code.json", {
    source: sources.industry,
    generatedAt: new Date().toISOString(),
    data: liepinIndustries,
  });
  writeJson("liepin_position_code.json", {
    source: sources.position,
    generatedAt: new Date().toISOString(),
    data: liepinPositionData,
  });
  writeJson("liepin_zhilian_industry_map.json", {
    source: sources.industry,
    generatedAt: new Date().toISOString(),
    summary: summarize(industryMappings),
    mappings: industryMappings,
  });
  writeJson("liepin_zhilian_position_map.json", {
    source: sources.position,
    generatedAt: new Date().toISOString(),
    summary: summarize(positionMappings),
    mappings: positionMappings,
  });

  console.log(
    JSON.stringify(
      {
        industries: liepinIndustries.length,
        positions: liepinPositions.length,
        industrySummary: summarize(industryMappings),
        positionSummary: summarize(positionMappings),
        sample: positionMappings.N0038,
      },
      null,
      2
    )
  );
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
