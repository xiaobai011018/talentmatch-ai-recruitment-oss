const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const guardSource = fs.readFileSync(
  path.join(__dirname, "../src/core/quoraApiGuard.js"),
  "utf8"
);

function createGuardContext(responseFactory) {
  const debugLogs = [];
  const alerts = [];
  const context = {
    URL,
    Response,
    location: { href: "chrome-extension://test/popup.html" },
    fetch: async (input, init) => responseFactory(input, init),
    alert: (message) => alerts.push(message),
    console: {
      debug: (...args) => debugLogs.push(args),
      error: () => {},
      log: () => {},
      warn: () => {},
    },
  };
  context.globalThis = context;
  vm.runInNewContext(guardSource, context);
  return { context, debugLogs, alerts };
}

test("401 invalid_api_key stops Quora response parsing and stays silent in UI", async () => {
  const { context, debugLogs, alerts } = createGuardContext(
    () =>
      new Response(JSON.stringify({ error: "invalid_api_key" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      })
  );

  let caughtError;
  await context
    .fetch("https://model.example.invalid/api/completions/quora.php", {
      method: "POST",
    })
    .catch((error) => {
      caughtError = error;
    });

  assert.equal(caughtError?.code, "QUORA_INVALID_API_KEY");
  assert.equal(caughtError?.silent, true);
  assert.equal(debugLogs.length, 1);
  assert.match(debugLogs[0][0], /AI 服务暂时不可用/);

  context.alert(caughtError);
  context.alert(`请求失败：${caughtError.message}`);
  assert.deepEqual(alerts, []);
});

test("other Quora 401 responses remain available to existing handlers", async () => {
  const { context, debugLogs } = createGuardContext(
    () => new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 })
  );

  const response = await context.fetch(
    "https://model.example.invalid/api/completions/quora.php"
  );

  assert.equal(response.status, 401);
  assert.equal(debugLogs.length, 0);
});

test("non-Quora requests are not intercepted", async () => {
  const { context, debugLogs } = createGuardContext(
    () =>
      new Response(JSON.stringify({ error: "invalid_api_key" }), {
        status: 401,
      })
  );

  const response = await context.fetch(
    "https://talent.example.invalid/api/example.php"
  );

  assert.equal(response.status, 401);
  assert.equal(debugLogs.length, 0);
});
