const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const backgroundSource = fs.readFileSync(
  path.join(__dirname, "../src/core/background.js"),
  "utf8"
);
const schedulerStart = backgroundSource.indexOf(
  'const BATCH_SCHEDULER_STORAGE_KEY'
);
const schedulerEnd = backgroundSource.indexOf(
  "chrome.runtime.onInstalled.addListener"
);
const schedulerSource = backgroundSource.slice(
  schedulerStart,
  schedulerEnd
);

test("通用消息监听器不会抢先响应批量调度消息", () => {
  const genericListenerStart = backgroundSource.indexOf(
    "chrome.runtime.onMessage.addListener",
    schedulerEnd
  );
  const genericListenerEnd = backgroundSource.indexOf(
    "function injectActivitySummaryIntoTab",
    genericListenerStart
  );
  const genericListenerSource = backgroundSource.slice(
    genericListenerStart,
    genericListenerEnd
  );

  assert.match(
    genericListenerSource,
    /message\.action !== "openPopup"[\s\S]*return false;/
  );
  assert.doesNotMatch(genericListenerSource, /no action taken/);
});

test("策略保存消息在 content script 未连接时自动注入并重试", () => {
  const popupSource = fs.readFileSync(
    path.join(__dirname, "../src/core/popup.js"),
    "utf8"
  );

  assert.match(
    popupSource,
    /function sendTabMessageWithContentScriptRetry\(tabId, message, callback\)/
  );
  assert.match(
    popupSource,
    /Could not establish connection\|Receiving end does not exist/
  );
  assert.match(
    popupSource,
    /files:\s*\[[\s\S]*src\/core\/quoraApiGuard\.js[\s\S]*src\/core\/content\.js[\s\S]*assets\/libs\/xlsx\.mini\.min\.js/
  );
  assert.match(popupSource, /send\(true\)/);
});

function createHarness(initialStoredState) {
  const storage = {};
  if (initialStoredState) {
    storage.talentMatchLiepinBatchScheduler =
      structuredClone(initialStoredState);
  }

  const context = {
    console: {
      error: () => {},
      log: () => {},
      warn: () => {},
    },
    chrome: {
      storage: {
        session: {
          async get(key) {
            return { [key]: structuredClone(storage[key]) };
          },
          async set(value) {
            Object.assign(storage, structuredClone(value));
          },
        },
      },
    },
  };
  context.globalThis = context;

  vm.runInNewContext(
    `${schedulerSource}
     let testInjectionCalls = 0;
     async function injectNextBatch() {
       testInjectionCalls++;
     }
     globalThis.schedulerHarness = {
       load: ensureBatchSchedulerStateLoaded,
       finish: finishBatchTab,
       setState(value) {
         batchSchedulerState = createEmptyBatchSchedulerState(value);
         batchSchedulerStateLoaded = true;
       },
       getState() {
         return JSON.parse(JSON.stringify(batchSchedulerState));
       },
       getInjectionCalls() {
         return testInjectionCalls;
       }
     };`,
    context
  );

  return { harness: context.schedulerHarness, storage };
}

test("乱序完成时只释放实际发送完成消息的标签页", async () => {
  const { harness, storage } = createHarness();
  harness.setState({
    active: true,
    runId: "run-1",
    allBatchTabIds: [101, 102, 103],
    nextInjectionIndex: 2,
    injectedTabIds: [101, 102],
    heartbeatByTab: { 101: 1, 102: 1 },
  });

  await harness.finish(102, {
    runId: "run-1",
    status: "completed",
  });

  assert.equal(
    JSON.stringify(harness.getState().injectedTabIds),
    JSON.stringify([101])
  );
  assert.equal(harness.getState().heartbeatByTab["102"], undefined);
  assert.equal(harness.getInjectionCalls(), 1);
  assert.deepEqual(
    storage.talentMatchLiepinBatchScheduler.injectedTabIds,
    [101]
  );
});

test("service worker 重启后从 session storage 恢复批次队列", async () => {
  const storedState = {
    active: true,
    runId: "persisted-run",
    params: { positionID: "position-1" },
    allBatchTabIds: [201, 202, 203],
    nextInjectionIndex: 2,
    injectedTabIds: [201, 202],
    heartbeatByTab: { 201: 100, 202: 200 },
    discoveryComplete: true,
    discoveryCompletedAt: 300,
    expectedBatchTabCount: 3,
  };
  const { harness } = createHarness(storedState);

  await harness.load();

  assert.equal(
    JSON.stringify(harness.getState()),
    JSON.stringify(storedState)
  );
});
