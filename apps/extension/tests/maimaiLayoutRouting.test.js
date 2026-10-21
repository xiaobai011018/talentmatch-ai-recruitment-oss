const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

test("脉脉新旧招聘搜索地址都进入匹配上传布局", () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, "../src/core/D.js"),
    "utf8"
  );
  const routeStart = source.indexOf(
    "currentTabUrl.includes('maimai.cn/ent/v41/recruit')"
  );
  const routeEnd = source.indexOf("showMaiMaiRecruitLayout();", routeStart);
  const fallbackStart = source.indexOf(
    'console.log("Mode：未知页面 - 使用Cookie专用布局")'
  );
  const routeBlock = source.slice(routeStart, routeEnd);

  assert.ok(routeStart >= 0, "缺少旧版脉脉招聘地址兼容");
  assert.ok(routeEnd > routeStart, "脉脉地址没有进入招聘布局");
  assert.ok(routeEnd < fallbackStart, "脉脉招聘路由必须先于未知页面兜底");
  assert.match(
    routeBlock,
    /currentTabUrl\.includes\('maimai\.cn\/ent\/talents\/discover\/search_v2'\)/
  );
});
