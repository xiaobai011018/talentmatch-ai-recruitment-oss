importScripts("quoraApiGuard.js");
importScripts("../utils/clientScreeningResumeFields.js");
importScripts("../utils/extractProcessedResumeField.js");
importScripts("../utils/highestEducation.js");

const BATCH_UPLOAD_LOCK_STORAGE_KEY = "talentMatchBatchUploadLock";

function normalizeBatchUploadLocks(raw) {
  if (!raw) return { tabs: {} };
  if (raw.tabs && typeof raw.tabs === "object") return raw;
  if (raw.tabId != null && raw.startedAt != null) {
    return { tabs: { [String(raw.tabId)]: { startedAt: raw.startedAt } } };
  }
  return { tabs: {} };
}

function setBatchUploadLockForTab(tabId, callback) {
  chrome.storage.local.get(BATCH_UPLOAD_LOCK_STORAGE_KEY, (data) => {
    const locks = normalizeBatchUploadLocks(data[BATCH_UPLOAD_LOCK_STORAGE_KEY]);
    locks.tabs[String(tabId)] = { startedAt: Date.now() };
    chrome.storage.local.set({ [BATCH_UPLOAD_LOCK_STORAGE_KEY]: locks }, callback);
  });
}

function releaseBatchUploadLockForTab(tabId, callback) {
  chrome.storage.local.get(BATCH_UPLOAD_LOCK_STORAGE_KEY, (data) => {
    const locks = normalizeBatchUploadLocks(data[BATCH_UPLOAD_LOCK_STORAGE_KEY]);
    delete locks.tabs[String(tabId)];
    if (Object.keys(locks.tabs).length === 0) {
      chrome.storage.local.remove(BATCH_UPLOAD_LOCK_STORAGE_KEY, callback);
    } else {
      chrome.storage.local.set({ [BATCH_UPLOAD_LOCK_STORAGE_KEY]: locks }, callback);
    }
  });
}

const BATCH_SCHEDULER_STORAGE_KEY = "talentMatchLiepinBatchScheduler";
const MAX_BATCH_INJECTIONS = 2;
const BATCH_HEARTBEAT_TIMEOUT_MS = 120000;

function createEmptyBatchSchedulerState(overrides = {}) {
  return {
    active: false,
    runId: "",
    params: null,
    allBatchTabIds: [],
    nextInjectionIndex: 0,
    injectedTabIds: [],
    heartbeatByTab: {},
    discoveryComplete: false,
    discoveryCompletedAt: 0,
    expectedBatchTabCount: 0,
    ...overrides,
  };
}

let batchSchedulerState = createEmptyBatchSchedulerState();
let batchSchedulerStateLoaded = false;
let batchSchedulerQueue = Promise.resolve();

function getBatchStorageArea() {
  return chrome.storage.session || chrome.storage.local;
}

async function ensureBatchSchedulerStateLoaded() {
  if (batchSchedulerStateLoaded) return;

  const stored = await getBatchStorageArea().get(
    BATCH_SCHEDULER_STORAGE_KEY
  );
  const raw = stored[BATCH_SCHEDULER_STORAGE_KEY];
  if (raw && typeof raw === "object") {
    batchSchedulerState = createEmptyBatchSchedulerState({
      ...raw,
      allBatchTabIds: Array.isArray(raw.allBatchTabIds)
        ? raw.allBatchTabIds
        : [],
      injectedTabIds: Array.isArray(raw.injectedTabIds)
        ? raw.injectedTabIds
        : [],
      heartbeatByTab:
        raw.heartbeatByTab && typeof raw.heartbeatByTab === "object"
          ? raw.heartbeatByTab
          : {},
    });
  }
  batchSchedulerStateLoaded = true;
}

async function persistBatchSchedulerState() {
  await getBatchStorageArea().set({
    [BATCH_SCHEDULER_STORAGE_KEY]: batchSchedulerState,
  });
}

function enqueueBatchScheduler(task) {
  const currentTask = batchSchedulerQueue.then(async () => {
    await ensureBatchSchedulerStateLoaded();
    return task();
  });
  batchSchedulerQueue = currentTask.catch((error) => {
    console.error("[Background] 批量调度状态处理失败:", error);
  });
  return currentTask;
}

function isCurrentBatchRun(runId) {
  return (
    !runId ||
    !batchSchedulerState.runId ||
    runId === batchSchedulerState.runId
  );
}

async function maybeFinishBatchRun() {
  const expectedTabsDiscovered =
    batchSchedulerState.expectedBatchTabCount === 0 ||
    batchSchedulerState.allBatchTabIds.length >=
      batchSchedulerState.expectedBatchTabCount;
  const discoveryGraceElapsed =
    batchSchedulerState.discoveryCompletedAt > 0 &&
    Date.now() - batchSchedulerState.discoveryCompletedAt >= 30000;

  if (
    batchSchedulerState.active &&
    batchSchedulerState.discoveryComplete &&
    (expectedTabsDiscovered || discoveryGraceElapsed) &&
    batchSchedulerState.nextInjectionIndex >=
      batchSchedulerState.allBatchTabIds.length &&
    batchSchedulerState.injectedTabIds.length === 0
  ) {
    batchSchedulerState.active = false;
    console.log(
      `[Background] 批次 ${batchSchedulerState.runId} 已全部处理完成`
    );
    await persistBatchSchedulerState();
  }
}

async function finishBatchTab(
  tabId,
  { runId = "", status = "completed", pauseBatch = false } = {}
) {
  if (tabId == null || !isCurrentBatchRun(runId)) {
    console.warn("[Background] 忽略非当前批次的终止消息:", {
      tabId,
      runId,
      currentRunId: batchSchedulerState.runId,
      status,
    });
    return false;
  }

  const wasInjected = batchSchedulerState.injectedTabIds.includes(tabId);
  batchSchedulerState.injectedTabIds =
    batchSchedulerState.injectedTabIds.filter((id) => id !== tabId);
  delete batchSchedulerState.heartbeatByTab[String(tabId)];

  if (pauseBatch) {
    batchSchedulerState.active = false;
    console.warn(
      `[Background] 批次 ${batchSchedulerState.runId} 因页面 ${tabId} 暂停: ${status}`
    );
  } else if (wasInjected) {
    console.log(
      `[Background] 页面 ${tabId} 已释放调度槽位，状态: ${status}`
    );
  }

  await persistBatchSchedulerState();

  if (!pauseBatch && batchSchedulerState.active) {
    await injectNextBatch();
    await maybeFinishBatchRun();
  }
  return wasInjected;
}

chrome.runtime.onInstalled.addListener(() => {
  console.log('Extension installed');
  chrome.contextMenus.create({
    id: "sendToAPI",
    title: "发送选中文本到API",
    contexts: ["selection"]
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('Message received:', message);
  if (message.action !== "openPopup" || !sender.tab) {
    // 不响应不属于该监听器的消息，否则会抢先占用其他监听器的
    // sendResponse（例如 startBatchInjection 的 success/runId 响应）。
    return false;
  }

  console.log('Opening popup for tab:', sender.tab.id);
  chrome.action.openPopup()
    .then(() => {
      console.log('Popup opened successfully');
      sendResponse({ status: "popup opened" });
    })
    .catch(error => {
      console.error('Error opening popup:', error);
      sendResponse({ status: "error", error: error });
    });
  return true;
});

function injectActivitySummaryIntoTab(tabId) {
  return chrome.scripting
    .executeScript({
      target: { tabId },
      files: [
        "src/core/quoraApiGuard.js",
        "src/core/linkedinActivitySummary.js",
      ],
    })
    .then(() =>
      chrome.scripting.executeScript({
        target: { tabId },
        func: () => window.__talentMatchRunActivitySummary?.(),
      })
    );
}

const activitySummaryProfilePendingTabs = new Set();

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  if (!activitySummaryProfilePendingTabs.has(tabId)) return;
  if (
    !tab.url ||
    !/linkedin\.com\/(?:in\/|sales\/lead\/|sales\/search)/i.test(tab.url)
  ) {
    return;
  }

  const returnedToSearch = /linkedin\.com\/sales\/search/i.test(tab.url);
  if (returnedToSearch) {
    activitySummaryProfilePendingTabs.delete(tabId);
  }
  console.log(
    `[Background] ActivitySummary ${returnedToSearch ? "搜索页返回" : "详情页"}加载完成，注入续跑:`,
    tab.url
  );
  setTimeout(() => {
    injectActivitySummaryIntoTab(tabId).catch((err) => {
      console.error("[Background] ActivitySummary 页面注入失败:", err);
    });
  }, 2000);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "resetButton") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      chrome.scripting.executeScript({
        target: { tabId: tabs[0].id },
        func: () => {
          const button = document.getElementById("MaiMaiUploadExcelButton");
          button.disabled = false;
          button.textContent = "上传Excel";
          button.style.background = "";
        }
      });
    });
  } else if (message.action === "startBatchInjection") {
    enqueueBatchScheduler(async () => {
      const runId =
        typeof globalThis.crypto?.randomUUID === "function"
          ? globalThis.crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      batchSchedulerState = createEmptyBatchSchedulerState({
        active: true,
        runId,
        params: message.params || {},
      });
      await persistBatchSchedulerState();
      console.log("[Background] 开始批量注入模式:", {
        runId,
        params: batchSchedulerState.params,
      });
      sendResponse({ success: true, runId });
    }).catch((error) => {
      sendResponse({ success: false, error: String(error) });
    });
    return true;
  } else if (message.action === "releaseBatchUploadLock") {
    const tabId = message.tabId ?? sender.tab?.id;
    if (tabId != null) {
      releaseBatchUploadLockForTab(tabId, () => sendResponse({ ok: true }));
    } else {
      sendResponse({ ok: false, error: "missing tabId" });
    }
    return true;
  } else if (message.action === "batchPageCompleted") {
    const tabId = message.tabId ?? sender.tab?.id;
    enqueueBatchScheduler(async () => {
      await finishBatchTab(tabId, {
        runId: message.runId,
        status: "completed",
      });
      sendResponse({ success: true });
    }).catch((error) => {
      sendResponse({ success: false, error: String(error) });
    });
    return true;
  } else if (message.action === "batchPageFailed") {
    const tabId = message.tabId ?? sender.tab?.id;
    enqueueBatchScheduler(async () => {
      await finishBatchTab(tabId, {
        runId: message.runId,
        status: message.reason || "failed",
        pauseBatch: message.pauseBatch === true,
      });
      sendResponse({ success: true });
    }).catch((error) => {
      sendResponse({ success: false, error: String(error) });
    });
    return true;
  } else if (message.action === "batchPageHeartbeat") {
    const tabId = message.tabId ?? sender.tab?.id;
    enqueueBatchScheduler(async () => {
      if (
        tabId != null &&
        isCurrentBatchRun(message.runId) &&
        batchSchedulerState.injectedTabIds.includes(tabId)
      ) {
        batchSchedulerState.heartbeatByTab[String(tabId)] = Date.now();
        await persistBatchSchedulerState();
      }
      sendResponse({ success: true });
    }).catch((error) => {
      sendResponse({ success: false, error: String(error) });
    });
    return true;
  } else if (message.action === "batchTabDiscoveryCompleted") {
    enqueueBatchScheduler(async () => {
      if (isCurrentBatchRun(message.runId)) {
        batchSchedulerState.discoveryComplete = true;
        batchSchedulerState.discoveryCompletedAt = Date.now();
        batchSchedulerState.expectedBatchTabCount = Math.max(
          0,
          Number(message.expectedBatchTabCount) || 0
        );
        await persistBatchSchedulerState();
        await injectNextBatch();
        await maybeFinishBatchRun();
      }
      sendResponse({ success: true });
    }).catch((error) => {
      sendResponse({ success: false, error: String(error) });
    });
    return true;
  } else if (message.action === "talentMatchActivitySummaryDone" && sender.tab?.id) {
    activitySummaryProfilePendingTabs.delete(sender.tab.id);
  } else if (message.action === "talentMatchActivitySummaryProfilePending" && sender.tab?.id) {
    activitySummaryProfilePendingTabs.add(sender.tab.id);
    console.log(
      "[Background] ActivitySummary 等待主页加载:",
      message.profileUrl,
      "tab=",
      sender.tab.id
    );
    sendResponse({ success: true });
    return true;
  } else if (message.action === "talentMatchInjectActivitySummary" && sender.tab?.id) {
    const tabId = sender.tab.id;
    injectActivitySummaryIntoTab(tabId)
      .then(() => sendResponse({ success: true }))
      .catch((err) => {
        console.error("[Background] ActivitySummary 注入失败:", err);
        sendResponse({ success: false, error: String(err) });
      });
    return true;
  }
});


// schedule a roughly once-every-5-seconds alarm
chrome.alarms.create("processMaiMai", { periodInMinutes: 10 / 60 });
chrome.alarms.create("liepinBatchWatchdog", { periodInMinutes: 1 });
//alarm for maimai(or it will be idle and mapping button will be useless)
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "processMaiMai") {
    // send a message into the tab to do one “step” of your pipeline
    chrome.tabs.query({ url: "*://maimai.cn/*" }, tabs => {
      for (let tab of tabs) {
        chrome.tabs.sendMessage(tab.id, { action: "processNextProfile" }); //content.js
      }
    });
  } else if (alarm.name === "liepinBatchWatchdog") {
    enqueueBatchScheduler(async () => {
      if (!batchSchedulerState.active) return;

      const now = Date.now();
      const timedOutTabIds = batchSchedulerState.injectedTabIds.filter(
        (tabId) =>
          now -
            Number(
              batchSchedulerState.heartbeatByTab[String(tabId)] || 0
            ) >
          BATCH_HEARTBEAT_TIMEOUT_MS
      );

      for (const tabId of timedOutTabIds) {
        console.error(
          `[Background] 页面 ${tabId} 心跳超时，释放槽位并继续下一页`
        );
        await finishBatchTab(tabId, {
          runId: batchSchedulerState.runId,
          status: "heartbeat-timeout",
        });
      }
      await maybeFinishBatchRun();
    });
  }
});

// 标签页关闭时自动释放该 Tab 的批量上传锁
chrome.tabs.onRemoved.addListener((tabId) => {
  releaseBatchUploadLockForTab(tabId, () => {
    console.log(`[Background] 标签页 ${tabId} 已关闭，自动释放批量上传锁`);
  });
  enqueueBatchScheduler(async () => {
    if (batchSchedulerState.injectedTabIds.includes(tabId)) {
      await finishBatchTab(tabId, {
        runId: batchSchedulerState.runId,
        status: "tab-closed",
      });
    }
  });
});

// 自动注入批量保存脚本到新打开的批量页面tab
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // 标签页刷新或导航时自动释放该 Tab 的批量上传锁
  if (changeInfo.status === 'loading') {
    releaseBatchUploadLockForTab(tabId, () => {
      console.log(`[Background] 标签页 ${tabId} 刷新/导航，自动释放批量上传锁`);
    });
  }

  enqueueBatchScheduler(async () => {
    if (!batchSchedulerState.active) return;

    const effectiveUrl = changeInfo.url || tab.url || "";
    const isBatchPage =
      effectiveUrl &&
      effectiveUrl
        .toLowerCase()
        .includes("liepin.com/resume/batchshowresume?token=batch");

    if (
      changeInfo.status === "loading" &&
      batchSchedulerState.injectedTabIds.includes(tabId)
    ) {
      await finishBatchTab(tabId, {
        runId: batchSchedulerState.runId,
        status: isBatchPage ? "tab-reloaded" : "navigated-away",
      });
      return;
    }

    if (
      changeInfo.status === "complete" &&
      isBatchPage &&
      !batchSchedulerState.allBatchTabIds.includes(tabId)
    ) {
      batchSchedulerState.allBatchTabIds.push(tabId);
      console.log(
        `[Background] 记录批量页面tabId: ${tabId}, 总数量: ${batchSchedulerState.allBatchTabIds.length}`
      );
      await persistBatchSchedulerState();
      await injectNextBatch();
    }
  });
});

// 注入下一批页面的函数
async function injectNextBatch() {
  if (!batchSchedulerState.active) return;

  // 检查是否还有页面需要注入
  if (
    batchSchedulerState.nextInjectionIndex >=
    batchSchedulerState.allBatchTabIds.length
  ) {
    console.log(
      `[Background] 当前已发现页面均已注入 (${batchSchedulerState.nextInjectionIndex}/${batchSchedulerState.allBatchTabIds.length})`
    );
    return;
  }

  // 检查当前活跃的注入数量（已注入但未完成的）
  const activeInjectionCount =
    batchSchedulerState.injectedTabIds.length;
  if (activeInjectionCount >= MAX_BATCH_INJECTIONS) {
    console.log(`[Background] 当前活跃注入数量已达上限 (${activeInjectionCount}/${MAX_BATCH_INJECTIONS})，等待完成后再注入`);
    return;
  }

  // 连续注入，直到达到限制或没有更多页面
  while (
    batchSchedulerState.active &&
    batchSchedulerState.nextInjectionIndex <
      batchSchedulerState.allBatchTabIds.length &&
    batchSchedulerState.injectedTabIds.length < MAX_BATCH_INJECTIONS
  ) {

    const tabId =
      batchSchedulerState.allBatchTabIds[
        batchSchedulerState.nextInjectionIndex
      ];
    console.log(
      `[Background] 注入第 ${batchSchedulerState.nextInjectionIndex + 1} 个批量页面 (tabId: ${tabId})`
    );

    // 检查是否有批量保存参数
    if (!batchSchedulerState.params) {
      console.warn("[Background] 没有找到批量保存参数，跳过注入");
      return;
    }

    batchSchedulerState.injectedTabIds.push(tabId);
    batchSchedulerState.nextInjectionIndex++;
    batchSchedulerState.heartbeatByTab[String(tabId)] = Date.now();
    await persistBatchSchedulerState();

    setBatchUploadLockForTab(tabId);

    const params = batchSchedulerState.params;
    const runId = batchSchedulerState.runId;

    // 先注入猎聘风控辅助脚本，再注入批量逻辑
    chrome.scripting
      .executeScript({
        target: { tabId: tabId },
        files: [
          "src/utils/liepinRiskControl.js",
          "src/utils/extractProcessedResumeField.js",
          "src/utils/clientScreeningResumeFields.js",
          "src/utils/highestEducation.js",
        ],
      })
      .then(() =>
        chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: async function (params, batchRunId) {
        let batchHeartbeatTimer = null;
        let batchTerminalMessageSent = false;

        function sendBatchHeartbeat() {
          try {
            chrome.runtime.sendMessage({
              action: "batchPageHeartbeat",
              runId: batchRunId,
            });
          } catch (_) {}
        }

        async function notifyBatchTerminal({
          status = "failed",
          reason = "unknown",
          pauseBatch = false,
        } = {}) {
          if (batchTerminalMessageSent) return;
          batchTerminalMessageSent = true;
          if (batchHeartbeatTimer) {
            clearInterval(batchHeartbeatTimer);
            batchHeartbeatTimer = null;
          }
          window.__talentMatchBatchRunning = false;
          try {
            await chrome.runtime.sendMessage({
              action: "releaseBatchUploadLock",
            });
          } catch (_) {}
          await chrome.runtime.sendMessage({
            action:
              status === "completed"
                ? "batchPageCompleted"
                : "batchPageFailed",
            runId: batchRunId,
            reason,
            pauseBatch,
          });
        }

        sendBatchHeartbeat();
        batchHeartbeatTimer = setInterval(sendBatchHeartbeat, 20000);

        try {
          console.log("[Injected Script] 开始执行自动批量保存脚本");

          // 使用从background.js传递的参数
          const selectedPositionKeywords = params.selectedPositionKeywords;
          const customJobRequirement = params.customJobRequirement;
          const positionName = params.positionName;
          const inchargeID = params.inchargeID;
          const positionID = params.positionID;
          const company_name = params.company_name;

          console.log("[Injected Script] 获取到的参数:", {
            selectedPositionKeywords,
            customJobRequirement,
            positionName,
            inchargeID,
            positionID,
            company_name
          });

          // 复制popup.js中LiepinBatchSaveResumeAlternative的injectedScript函数体

          console.log(
            "从 popup.js 接收到的数据:",
            selectedPositionKeywords,
            customJobRequirement
          );

          async function sendPromptToAPI(prompt, url, mode = "defaultMode") {
            const formData = new FormData();
            let apiURL = "";

            if (mode == "getStandardResume") {
              apiURL = "https://model.example.invalid/api/completions/quora.php";
              formData.append("chatbotID", "__TALENTMATCH_MODEL_07__");
              formData.append("userID", "__TALENTMATCH_USER_01__");
              formData.append("prompt", prompt);
              formData.append("permission", "1");
            } else if (mode == "ListBot") {
              apiURL = "https://model.example.invalid/api/completions/quora.php";
              formData.append("chatbotID", "__TALENTMATCH_MODEL_04__");
              formData.append("userID", "__TALENTMATCH_USER_01__");

              const initialScreeningRegex = /初筛：([\s\S]*?)(?=深匹)/;
              const personalInfoRegex = /个人信息([\s\S]*)/;
              const initialMatch = prompt.match(initialScreeningRegex);
              const personalInfoMatch = prompt.match(personalInfoRegex);
              if (initialMatch && personalInfoMatch) {
                prompt = `${initialMatch[0]} ${personalInfoMatch[0]}`;
              } else if (initialMatch) {
                prompt = initialMatch[0];
              }
              formData.append("prompt", prompt);
              formData.append("permission", "1");
            } else {
              apiURL = "https://model.example.invalid/api/completions/quora.php";
              formData.append("chatbotID", "__TALENTMATCH_MODEL_05__");
              formData.append("userID", "__TALENTMATCH_USER_01__");

              const deepMatchRegex = /深匹([\s\S]*?)(?=个人信息)/;
              const personalInfoRegex = /个人信息([\s\S]*)/;
              const deepMatch = prompt.match(deepMatchRegex);
              const personalInfoMatch = prompt.match(personalInfoRegex);
              if (deepMatch && personalInfoMatch) {
                prompt = `${deepMatch[0]} \n ${personalInfoMatch[0]}`;
              } else if (deepMatch) {
                prompt = deepMatch[0];
              }
              formData.append("prompt", prompt);
              formData.append("permission", "1");
            }

            try {
              const response = await fetch(apiURL, {
                method: "POST",
                body: formData,
              });

              if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
              }

              const result = await response.json();
              let content = result.choices[0].message.content;
              console.log("API response:", result);
              console.log("API response String:", content);

              return content;
            } catch (error) {
              console.error("Error sending prompt to API:", error);
            }
          }

          async function sendResumeData(
            content,
            positionName,
            keywords,
            result,
            isElite,
            note,
            factCheckResult = "",
            Duplicateresult = "",
            upload_status = "",
            activity_time = ""
          ) {
            console.log(`
              批量keywords:
              ${JSON.stringify(keywords)}
              
              `);
            const keywordString = [
              keywords.workInfoContent ? keywords.workInfoContent : "",
              keywords.eduInfoContent?.schoolName || "",
              keywords.eduInfoContent?.schoolSpecial || "",
            ]
              .filter(Boolean)
              .join(" ")
              .trim();

            const data = {
              positionName: positionName,
              detailedResume: content,
              keywords: keywordString,
              result: result,
              is_elite: isElite == true ? "y" : "", // 新增 is_elite 字段
              note: note, // 新增 note 字段
              factCheck: factCheckResult ? factCheckResult : "",
              duplicate: Duplicateresult ? Duplicateresult : "",
              upload_status: upload_status ? upload_status : "",
              lastLoginDate: activity_time,
            };

            try {
              const response = await fetch(
                "http://localhost:8000/LiepinResumeBatchSave/",
                {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify(data),
                }
              );

              const contentType = response.headers.get("content-type");
              if (!contentType || !contentType.includes("application/json")) {
                throw new Error("服务器返回的不是 JSON 格式的响应");
              }

              const responseData = await response.json();
              console.log("成功发送简历数据:", responseData);
            } catch (error) {
              console.error("发送简历数据时出错:", error);
            }

          }

          async function handleBatchSave(selectedPositionName) {
            console.log(
              `handleBatchSave 函数在页面中执行，职位名称为 ${selectedPositionName}`
            );
            if (window.__talentMatchBatchRunning) {
              console.warn("当前页面已有批量任务在运行，跳过重复注入");
              if (batchHeartbeatTimer) {
                clearInterval(batchHeartbeatTimer);
                batchHeartbeatTimer = null;
              }
              return;
            }
            window.__talentMatchBatchRunning = true;

            // 等待页面和iframe完全加载
            console.log("[Injected Script] 等待页面和iframe加载...");
            await new Promise(resolve => setTimeout(resolve, 2000));

            let iframe = document.querySelector('iframe[src^="/resume/showresumedetail/"]');
            if (!iframe || iframe.tagName.toLowerCase() !== "iframe") {
              console.error("未找到指定的 iframe，等待2秒后重试...");
              // 再等待2秒后重试
              await new Promise(resolve => setTimeout(resolve, 2000));

              const iframeRetry = document.querySelector('iframe[src^="/resume/showresumedetail/"]');
              if (!iframeRetry || iframeRetry.tagName.toLowerCase() !== "iframe") {
                console.error("重试后仍未找到指定的 iframe，退出处理");
                await notifyBatchTerminal({
                  reason: "resume-iframe-not-found",
                });
                return;
              }
              iframe = iframeRetry;
              console.log("[Injected Script] 重试后找到iframe，继续处理");
            } else {
              console.log("[Injected Script] 找到iframe，继续处理");
            }

            const iframeDocument =
              iframe.contentDocument || iframe.contentWindow.document;
            if (!iframeDocument) {
              console.error("无法访问 iframe 的内容");
              await notifyBatchTerminal({
                reason: "resume-iframe-inaccessible",
              });
              return;
            }

            const spans = document.querySelectorAll(".ac0Qm, ._40231ac0Qm");
            let index = 0;

            function getLiepinKeywords(iframeDocument) {
              let result = {};

              const workInfoItems =
                iframeDocument.querySelector(".rd-work-info-head");
              const workJobTitle = iframeDocument.querySelector(`.job-name`);

              if (workInfoItems) {
                result.workInfoContent = workInfoItems.textContent
                  .trim()
                  .replace(/（.*$/, "")
                  .trim();
              } else {
              }

              if (workJobTitle) {
                result.workInfoContent += ` ${workJobTitle.textContent.trim()}`;
              } else {
              }

              const eduInfo = iframeDocument.querySelector(
                ".resume-detail-edu-info"
              );
              if (eduInfo) {
                const schoolName = eduInfo.querySelector(".school-name");
                const schoolSpecial = eduInfo.querySelector(".school-special");

                result.eduInfoContent = {
                  schoolName: schoolName ? schoolName.textContent.trim() : "",
                  schoolSpecial: schoolSpecial
                    ? schoolSpecial.textContent.trim()
                    : "",
                };
              }

              // 检查是否在iframe环境中
              const targetDocument = typeof iframeDocument !== 'undefined' ? iframeDocument : document;
              console.log("当前操作的文档:", targetDocument === document ? "主文档" : "iframe文档");
              
              // 首先尝试原始的iframe查找逻辑（修正类名）
              let lastLoginSpan = Array.from(
                targetDocument.querySelectorAll('div._40231BTVlw span')
              ).find(el => el.textContent?.includes('最后一次登录时间'));
              
              // 如果没找到，尝试更广泛的匹配
              if (!lastLoginSpan) {
                // 查找包含"登录时间"的所有span
                const loginSpans = Array.from(targetDocument.querySelectorAll('span')).filter(el => {
                  const text = el.textContent?.trim() || '';
                  return text.includes('最后一次登录时间') || text.includes('最后登录时间');
                });
                
                console.log("找到的登录相关span:", loginSpans.map(el => el.textContent.trim()));
                lastLoginSpan = loginSpans[0];
              }

              if (lastLoginSpan) {
                const text = lastLoginSpan.textContent.trim();
                console.log("找到的登录时间元素文本:", text);

                // 检查是否有隐私保护
                if (text.includes('隐私保护')) {
                  console.log("用户设置了隐私保护，无法获取登录时间");
                  result.lastLoginDate = '隐私保护';
                } else {
                  // 用正则提取日期部分
                  const match = text.match(/(\d{4}\/\d{2}\/\d{2})/);
                  if (match) {
                    const lastLoginDate = match[1];
                    console.log("提取到的日期:", lastLoginDate);
                    result.lastLoginDate = lastLoginDate;
                  } else {
                    console.warn("正则匹配不到日期，原始文本:", text);
                    result.lastLoginDate = '';
                  }
                }
              } else {
                console.warn("没有找到包含 '最后一次登录时间' 的 span");
                result.lastLoginDate = '';
              }

              return result;
            }
            let firstRun = true;

            async function clickAndLogNextSpan() {
              if (window.TalentMatchLiepinRisk?.isBatchPausedOnVerification?.()) {
                console.warn("[TalentMatch Liepin] 验证暂停中，停止切换简历");
                await notifyBatchTerminal({
                  reason: "verification-required",
                  pauseBatch: true,
                });
                return;
              }

              const activeSpan = document.querySelector("._40231ac0Qm._40231SJOwc, .ac0Qm.SJOwc");
              console.log(activeSpan)
              if (activeSpan) {
                const activeIndex = Array.from(spans).indexOf(activeSpan);
                if (activeIndex !== -1) {
                  if (firstRun) {
                    index = activeIndex; // 第一次执行时从当前激活的元素开始
                  } else if (activeIndex + 1 < spans.length) {
                    index = activeIndex + 1; // 后续执行时从当前激活元素的下一个元素开始
                  }
                }
              }
              firstRun = false; // 无论是否找到激活项，第一次调用后始终重置

              if (index < spans.length) {
                spans[index].click();

                // 增加简历查看数到人才库H5
                const formData = new URLSearchParams();
                formData.append('position_id', positionID);
                formData.append('count_resume_reviews', 1);

                // Send POST request
                fetch('https://talent.example.invalid/api/add_data_count.php', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                  },
                  body: formData.toString(),
                })
                  .then(response => {
                    if (!response.ok) {
                      throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json(); // or .text() depending on the API's response format
                  })
                  .then(data => {
                    console.log('API response:', data);
                  })
                  .catch(error => {
                    console.error('Error calling API:', error);
                  });

                console.log("简历查看数+1")

                const formData2 = new URLSearchParams();
                formData2.append('position_id', positionID);
                formData2.append('ai_process_status', "初筛上传中");

                // // Send POST request
                // fetch('https://talent.example.invalid/api/update_ai_status.php', {
                //   method: 'POST',
                //   headers: {
                //     'Content-Type': 'application/x-www-form-urlencoded',
                //   },
                //   body: formData2.toString(),
                // })
                //   .then(response => {
                //     if (!response.ok) {
                //       throw new Error(`HTTP error! Status: ${response.status}`);
                //     }
                //     return response.json(); // or .text() depending on the API's response format
                //   })
                //   .then(data => {
                //     console.log('API response:', data);
                //   })
                //   .catch(error => {
                //     console.error('Error calling API:', error);
                //   });

                // console.log("修改岗位上传为初筛上传中")

                setTimeout(async () => {
                  function sleep(ms) {
                    return new Promise((resolve) => setTimeout(resolve, ms));
                  }

                  async function retryProcess() {
                    const risk = window.TalentMatchLiepinRisk;
                    if (!risk) {
                      console.error("[TalentMatch Liepin] liepinRiskControl 未注入");
                      return null;
                    }
                    return risk.extractResumeContentFromIframe();
                  }

                  // 开始重试流程
                  const content = await retryProcess();

                  if (content !== null) {
                    const iframe = document.querySelector('iframe[src^="/resume/showresumedetail/"]');
                    const iframeDocument =
                      iframe.contentDocument || iframe.contentWindow.document;
                    const keywords = getLiepinKeywords(iframeDocument);
                    const prompt = `简历信息：${customJobRequirement
                      ? customJobRequirement
                      : selectedPositionKeywords
                      } \n个人信息：${content}`;



                    let outputFifteenDaysAgo = "";  // 用来保存15天之前的内容
                    let outputOlderThanFifteenDays = ""; // 保存15天以前的内容
                    let hasRecordFifteenDaysAgo = false; // 标记是否有15天内的内容

                    try {
                      let factCheckResult = ""
                      let Duplicateresult = ""

                      let result;
                      let attempts = 0;
                      let maxAttempts = 5;

                      try {
                        while (attempts < maxAttempts) {
                          try {
                            result = await sendPromptToAPI(
                              prompt,
                              "YOUR_PROMPT_API_URL",
                              "defaultMode"
                            );
                            if (typeof result === "string") {
                              break; // If result is a string, break out of the retry loop
                            }
                          } catch (err) {
                            console.warn(`Attempt ${attempts + 1} failed:`, err);
                          }

                          attempts++;
                          if (attempts < maxAttempts) {
                            console.log(`Retrying in 2 seconds...`);
                            await new Promise((resolve) =>
                              setTimeout(resolve, 2000)
                            );
                          }
                        }
                      } catch {
                        console.log("AI有5次没有返回内容，跳过当前人")
                        return null
                      }

                      if (typeof result !== "string") {
                        throw new Error(
                          "Failed to fetch a valid result from the API after 5 attempts."
                        );
                      }

                      // --- 查找金领标签 (is_elite) ---
                      let eliteTags =
                        iframeDocument.querySelectorAll("span.elite-tag");
                      let isElite = eliteTags.length > 0 ? true : false;
                      console.log("是否为金领:", isElite);

                      //格式化最近活跃时间
                      console.log("最后一次登录时间是：", keywords.lastLoginDate);
                      let activity_time = keywords.lastLoginDate.includes("：") ? keywords.lastLoginDate.split("：")[1].trim().replace(/\//g, "-") + " 00:00:00" : keywords.lastLoginDate.replace(/\//g, "-") + " 00:00:00"

                      // --- 查找所有 note  的 textContent 合并成字符串 ---
                      const viewAllNotesButton = iframeDocument.querySelector('.c-view-detail');

                      if (viewAllNotesButton) {
                        viewAllNotesButton.click();
                        console.log('点击了：查看全部备注');
                      } else {
                        console.log('未找到 查看全部备注 按钮');
                      }

                      await new Promise((resolve) => setTimeout(resolve, 500));

                      const DetailsTime = iframeDocument.querySelectorAll(
                        ".resume-node-drawer-list .time"
                      );
                      const nodeDetails = iframeDocument.querySelectorAll(
                        ".resume-node-drawer-list .cont"
                      );
                      let output = "";  // 保留原本的 output 拼接

                      // 获取当前日期
                      const currentDate = new Date();

                      // 计算15天前的日期
                      const fifteenDaysAgo = new Date();
                      fifteenDaysAgo.setDate(currentDate.getDate() - 15);


                      // 判断 DetailsTime 和 nodeDetails 是否有效并且长度相同


                      if (DetailsTime.length > 0 && nodeDetails.length > 0 && DetailsTime.length === nodeDetails.length) {
                        for (let i = 0; i < DetailsTime.length; i++) {
                          const timeText = DetailsTime[i].textContent.trim(); // 获取时间元素的文本内容
                          const detailText = nodeDetails[i].textContent.trim(); // 获取对应的节点详情内容

                          // 拼接原始的 output 内容
                          output += `备注：[${timeText}] [${detailText}]\n`;

                          // 将 timeText 转换为 Date 对象
                          const timeParts = timeText.split(" "); // 假设时间格式是 "yyyy/MM/dd HH:mm"
                          const [year, month, day] = timeParts[0].split("/").map(num => parseInt(num, 10));
                          const [hour, minute] = timeParts[1].split(":").map(num => parseInt(num, 10));

                          const timeDate = new Date(year, month - 1, day, hour, minute);

                          // 判断时间是否在15天之内
                          if (timeDate >= fifteenDaysAgo) {
                            outputFifteenDaysAgo += `[${timeText}]:[${detailText}]\n=========\n`;
                            hasRecordFifteenDaysAgo = true; // 发现有15天内的记录
                          } else {
                            outputOlderThanFifteenDays += `[${timeText}]:[${detailText}]\n=========\n`;
                          }
                        }

                        console.log("拼接结果:\n", output);
                        console.log("15天之内的内容:\n", outputFifteenDaysAgo);
                        console.log("15天以前的内容:\n", outputOlderThanFifteenDays);
                        console.log("15天内是否有记录: ", hasRecordFifteenDaysAgo);
                      } else {
                        console.log("DetailsTime 和 nodeDetails 数量不一致或为空");
                      }

                      note = output;
                      let upload_status;
                      // 深匹过了标志
                      let DFPassed = !result.includes("不匹配");

                      // 不匹配与是都会事实检查
                      if (1) {
                        if (
                          result.includes("非常匹配") ||
                          result.includes("匹配") ||
                          result.includes("不确定")
                        ) {
                          console.log(`准备进行事实检查`);

                          // 生成 factPrompt 的内容
                          function extractContentBetweenDeepAndRaw(prompt) {
                            // 弹出prompt内容
                            console.log(`Input:${prompt}`);

                            // 正则表达式匹配"深匹要求："到"raw"之间的内容
                            const regex = /深匹要求[\s\S]*?(.*?)raw/;
                            const match = prompt.match(regex);

                            // 如果匹配到，返回匹配的内容，否则返回null
                            return match ? match[1].trim() : prompt;
                          }

                          const jobRequirement = customJobRequirement ? customJobRequirement : selectedPositionKeywords

                          function extractContentBetweenDeepAndRaw(prompt) {
                            // 弹出prompt内容
                            console.log(`Input:${prompt}`);

                            // 正则表达式匹配"深匹要求："到"raw"之间的内容
                            const regex = /深匹要求[\s\S]*?(.*?)raw/;
                            const match = prompt.match(regex);

                            // 如果匹配到，返回匹配的内容，否则返回null
                            return match ? match[1].trim() : prompt;
                          }


                          const factPrompt = `requirement: ${extractContentBetweenDeepAndRaw(jobRequirement + "raw")}\n raw resume：${content}，comment：${result}`;
                          // 准备 factPrompt 的请求
                          const formData = new FormData();

                          formData.append(
                            "chatbotID",
                            "__TALENTMATCH_MODEL_06__"
                          );
                          formData.append(
                            "userID",
                            "__TALENTMATCH_USER_01__"
                          );
                          formData.append("prompt", factPrompt);
                          formData.append("permission", "1");

                          // 发送请求到 factPrompt 接口
                          const response = await fetch(
                            "https://model.example.invalid/api/completions/quora.php",
                            {
                              method: "POST",
                              body: formData,
                            }
                          );


                          let responseData = await response.json();
                          responseData = responseData?.choices?.[0]?.message?.content;

                          // 检查返回内容是否包含“是”
                          // 目前去重常做
                          if (!responseData.includes("不匹配") || DFPassed == true) {
                            // if (1) {
                            console.log(`通过，准备发送到 anyjob!`);
                            factCheckResult = responseData

                            // 解析 keywords，确保是一个对象
                            let parsedKeywords;
                            try {
                              parsedKeywords =
                                typeof keywords === "string"
                                  ? JSON.parse(keywords)
                                  : keywords;
                            } catch (e) {
                              console.error("Failed to parse keywords:", e);
                              parsedKeywords = {};
                            }

                            // 提取 currentCompany 和 currentPosition
                            const workInfo = parsedKeywords.workInfoContent || "";
                            const [currentCompany, currentPosition] = workInfo
                              .split(/\s(.+)/) // 分割为公司和职位
                              .filter(Boolean) // 过滤掉空值
                              .map((item, index) =>
                                index === 1 && item.length > 20 ? item.slice(0, 20) + '...' : item
                              ); // 限制职位长度为20字


                            // 获取公司ID
                            async function getCompanyId(companyName) {
                              try {
                                // 准备表单数据
                                const data = new URLSearchParams();
                                data.append("company_name", companyName);

                                const response = await fetch("https://talent.example.invalid/api/get_company_id.php", {
                                  method: "POST",
                                  headers: {
                                    "Content-Type": "application/x-www-form-urlencoded"
                                  },
                                  body: data.toString()
                                });

                                if (!response.ok) {
                                  throw new Error(`HTTP error! status: ${response.status}`);
                                }

                                const result = await response.json();
                                console.log("Company ID API response:", result);
                                return result;
                              } catch (error) {
                                console.error("Error getting company ID:", error);
                                return null;
                              }
                            }

                            async function extractCompanyIDs(result) {
                              if (result && result.status === 'found' && Array.isArray(result.data)) {
                                return result.data.map(item => item.company_id);
                              }
                              return [];
                            }

                            const currentCompanyID = await getCompanyId(currentCompany);
                            const selectedCompanyID = await getCompanyId(company_name);

                            const currentIDs = await extractCompanyIDs(currentCompanyID);
                            const selectedIDs = await extractCompanyIDs(selectedCompanyID);

                            console.log("currentCompanyIDs:", currentIDs);
                            console.log("selectedCompanyIDs:", selectedIDs);

                            // 比较两个数组是否有交集
                            const hasCommonID = currentIDs.some(id => selectedIDs.includes(id));

                            if (hasCommonID) {
                              console.log("此候选人当前在该岗位工作，不保存，跳过");
                              index++;
                              await clickAndLogNextSpan();
                              return;
                            }

                            function processKeywordsA(inputKeywords) {
                              console.log(`给去重用的关键词处理1\n${inputKeywords}`);

                              // 去除 "实习生" 和 "实习"
                              let cleanedKeywords = inputKeywords.replace(/实习生/g, "").replace(/实习/g, "");

                              // 计算字符串长度，中文字符算2个字符，英文字符算1个字符
                              function calculateLength(str) {
                                var length = 0;
                                for (var i = 0; i < str.length; i++) {
                                  var char = str.charAt(i);
                                  if (char.match(/[\u4e00-\u9fa5]/)) {
                                    // 中文字符范围
                                    length += 2;
                                  } else {
                                    length += 1;
                                  }
                                }
                                return length;
                              }

                              // 检查字符串总长度是否超过56个字符
                              const length = calculateLength(cleanedKeywords);
                              if (length > 56) {
                                // 计算空格位置，最多截取到第5个空格之前
                                let spaceCount = 0;
                                let lastSpaceIndex = -1;

                                // 遍历字符串，找到第5个空格的位置
                                for (let i = 0; i < cleanedKeywords.length; i++) {
                                  if (cleanedKeywords[i] === " ") {
                                    spaceCount++;
                                    if (spaceCount === 5) {
                                      lastSpaceIndex = i;
                                      break;
                                    }
                                  }
                                }

                                // 如果找到了第5个空格，则截取到该空格之前
                                if (lastSpaceIndex !== -1) {
                                  cleanedKeywords = cleanedKeywords.substring(0, lastSpaceIndex);
                                } else {
                                  // 如果没有5个空格，按照原逻辑截取
                                  cleanedKeywords = cleanedKeywords.substring(0, 56);
                                }
                              }

                              // 输出返回的关键词
                              console.log(`给去重用的关键词处理2：\n${cleanedKeywords}`);

                              return cleanedKeywords;
                            }

                            // 构造 liepin_keywords
                            const liepinKeywords = [
                              workInfo,
                              parsedKeywords.eduInfoContent?.schoolName || "",
                              parsedKeywords.eduInfoContent?.schoolSpecial || "",
                            ].join(" ");

                            // 发送请求（或者仅打印请求体取决于某变量的值）
                            let shouldSend = 0;

                            // 发送 liepin_keywords 检查是否重复
                            const duplicateCheckFormData = new FormData();
                            duplicateCheckFormData.append("permission", "1");
                            duplicateCheckFormData.append("link", "");
                            duplicateCheckFormData.append("liepin_keywords", liepinKeywords);
                            duplicateCheckFormData.append("user_id", inchargeID);

                            try {
                              const duplicateCheckResponse = await fetch(
                                "https://talent.example.invalid/api/duplicate_screening_resume.php",
                                {
                                  method: "POST",
                                  body: duplicateCheckFormData,
                                }
                              );
                              const duplicateCheckData = await duplicateCheckResponse.json();
                              console.log("Duplicate check response:", duplicateCheckData);

                              // 检查 duplicate 字段值
                              if (duplicateCheckData.duplicate === "no") {
                                console.log("批量简历上传AnyJob 新候选人");
                                console.log("No duplicate found. Setting shouldSend to 1.");
                                shouldSend = 1;
                                Duplicateresult = "No"
                              } else {
                                // 初始化 Duplicateresult
                                Duplicateresult = "Yes";

                                // 遍历 duplicateCheckData.records 数组
                                for (let i = 0; i < duplicateCheckData.records.length; i++) {
                                  // 获取当前对象的 position_id 和 positionID 的值进行比较
                                  if (duplicateCheckData.records[i].position_id == positionID) {
                                    // 如果 position_id 与变量 positionID 相同，直接设置 Duplicateresult 为 "Yes"
                                    Duplicateresult = "Yes";
                                    shouldSend = 0
                                    console.log("批量简历上传AnyJob 该岗位已经存在的候选人");
                                    console.log("Duplicate found. shouldSend remains 0.");

                                    // lastLoginDate = Array.from(
                                    //   document.querySelectorAll('div.BTVlw span')
                                    // ).find(el => el.textContent.includes('最后一次登录时间'));
                                    // if (lastLoginDate) {
                                    //   lastLoginDate = lastLoginDate.textContent;
                                    //   lastLoginDate = lastLoginDate.replace("最后一次登录时间", "登陆时间");

                                    //   lastLoginDate = lastLoginDate.split("：")[1].trim().replace(/\//g, "-") + " 00:00:00"
                                    // } else {
                                    //   console.log('找不到 span 元素');
                                    //   lastLoginDate = ""
                                    // }


                                    async function updateAllDuplicateTimes(activity_time) {
                                      for (let i = 0; i < duplicateCheckData.records.length; i++) {
                                        let screening_id = duplicateCheckData.records[i].id
                                        try {
                                          console.log(`Updating screening_id: ${screening_id}`)
                                          await updateDuplicateTime(screening_id, activity_time)
                                          console.log(`Successfully updated screening_id: ${screening_id}`)
                                        } catch (error) {
                                          alert(error)
                                        }
                                      }
                                    }
                                    console.log(`activity_time: ${activity_time}`)
                                    await updateAllDuplicateTimes(activity_time)



                                    async function updateDuplicateTime(screening_id, activity_time) {
                                      const data = new URLSearchParams();
                                      data.append('screening_id', screening_id);
                                      data.append('activity_time', activity_time);
                                      try {
                                        const response = await fetch('https://talent.example.invalid/api/update_activity_time.php', {
                                          method: 'POST',
                                          headers: {
                                            'Content-Type': 'application/x-www-form-urlencoded'
                                          },
                                          body: data
                                        });

                                        const result = await response.json();
                                        console.log(`UPDATE SUCCESSFULLY`)
                                      } catch (error) {
                                        alert(error)
                                      }
                                    }

                                    break;  // 找到重复项后，跳出循环



                                  } else {
                                    console.log(`候选人存在但不是同一个岗位`)
                                    console.log(`${duplicateCheckData.records[i].position_id} == ${positionID}`)
                                    shouldSend = 1
                                    async function updateAllDuplicateTimes(activity_time) {
                                      for (let i = 0; i < duplicateCheckData.records.length; i++) {
                                        let screening_id = duplicateCheckData.records[i].id
                                        try {
                                          console.log(`Updating screening_id: ${screening_id}`)
                                          await updateDuplicateTime(screening_id, activity_time)
                                          console.log(`Successfully updated screening_id: ${screening_id}`)
                                        } catch (error) {
                                          alert(error)
                                        }
                                      }
                                    }
                                    console.log(`activity_time: ${activity_time}`)
                                    await updateAllDuplicateTimes(activity_time)



                                    async function updateDuplicateTime(screening_id, activity_time) {
                                      const data = new URLSearchParams();
                                      data.append('screening_id', screening_id);
                                      data.append('activity_time', activity_time);
                                      try {
                                        const response = await fetch('https://talent.example.invalid/api/update_activity_time.php', {
                                          method: 'POST',
                                          headers: {
                                            'Content-Type': 'application/x-www-form-urlencoded'
                                          },
                                          body: data
                                        });

                                        const result = await response.json();
                                        console.log(`UPDATE SUCCESSFULLY`)
                                      } catch (error) {
                                        alert(error)
                                      }
                                    }
                                    // 如果 position_id 不相同，提取 Position 属性的文本并追加到 Duplicateresult
                                    Duplicateresult += "，" + duplicateCheckData.records[i].Position;
                                  }
                                }

                                console.log("批量简历上传AnyJob 其他岗位已经存在的候选人");
                                console.log("依旧上传");
                              }

                              if (responseData.includes("不匹配")) {
                                console.log(`事实检查不匹配，不上传`)
                                shouldSend = 0
                              }
                            } catch (error) {
                              console.log("Error checking duplicate:", error);
                            }

                            const removeEmojisAndNotNeededPart = (text) => {
                              // 移除文本中的表情符号和 "备注内容简历洞察一秒洞" 及其后续内容
                              return text.replace(
                                /[\uD800-\uDBFF][\uDC00-\uDFFF]|[\u2300-\u27BF]|[\u2B50\u2665\u2764\uD83D\uDC9C\uD83C\uDF0F\uD83D\uDD25\uD83D\uDCA1\uD83D\uDC8C\uD83D\uDC8B\uD83D\uDE00-\uDE4F\uD83E\uDD00-\uDDFF]|备注内容简历洞察一秒洞.*/g,
                                ''
                              );
                            };


                            const myHeaders = new Headers();
                            const formdata = new FormData();

                            async function fetchChatbotResponse(prompt = "") {
                              const formData = new FormData();

                              // 添加固定参数
                              formData.append("chatbotID", "__TALENTMATCH_MODEL_08__");
                              formData.append("userID", "__TALENTMATCH_USER_01__");
                              formData.append("prompt", prompt);
                              formData.append("permission", "1");

                              try {
                                const response = await fetch('https://model.example.invalid/api/completions/quora.php', {
                                  method: 'POST',
                                  body: formData,
                                });

                                const data = await response.json();

                                // 提取 content 字段
                                return data.choices[0]?.message?.content || null;
                              } catch (error) {
                                console.error("Error fetching chatbot response:", error);
                                return null;
                              }
                            }
                            async function getAiSummary(prompt, botID) {
                              const formData = new FormData();
                              let apiURL = "https://model.example.invalid/api/completions/quora.php";
                              formData.append("chatbotID", botID);
                              formData.append("userID", "__TALENTMATCH_USER_01__");
                              formData.append("prompt", prompt);
                              formData.append("permission", "1");

                              try {
                                const response = await fetch(apiURL, {
                                  method: "POST",
                                  body: formData,
                                });

                                if (!response.ok) {
                                  throw new Error(`HTTP error! status: ${response.status}`);
                                }

                                const result = await response.json();
                                let content = result.choices[0].message.content;
                                console.log("API response String:", content);
                                return content;
                              } catch (error) {
                                console.error("Error sending prompt to API:", error);
                                return null;
                              }
                            }

                            const processedResume = await fetchChatbotResponse(removeEmojisAndNotNeededPart(content))
                            console.log(`【测试】processedResume: ${processedResume}`)

                            const ai_summary = await getAiSummary(content, "__TALENTMATCH_MODEL_19__");
                            console.log(`ai_summary : ${ai_summary}`);

                            const factCheckComment = factCheckResult.slice(factCheckResult.indexOf("，", factCheckResult.indexOf("，") + 1) + 1);

                            const name = extractProcessedResumeCandidateName(processedResume, content);
                            console.log("【测试】提取名字：", name)

                            formdata.append("permission", "1");
                            formdata.append("position_id", positionID);
                            formdata.append("name", name);
                            formdata.append("current_company", currentCompany);
                            formdata.append("current_position", currentPosition);
                            formdata.append("link", "");
                            formdata.append("liepin_keywords", liepinKeywords);
                            formdata.append("resume_content", processedResume);
                            formdata.append("incharge_id", inchargeID);
                            formdata.append("user_id", inchargeID);
                            formdata.append("coins_cost", 2);
                            formdata.append("ai_summary", ai_summary);

                            formdata.append('activity_time', activity_time)

                            const tagsRaw = extractProcessedResumeField(processedResume, "优势标签", {
                              loosePrefix: true,
                            });
                            if (tagsRaw) {
                              const tags = tagsRaw.split(/[,，]/).map(t => t.trim()).filter(t => t).join(",");
                              formdata.append("tags", tags);
                            }
                            // REQ_zwuZRpc7pcMFa9NOpdO6O8BMuhtciAUj

                            // Match phone and WeChat using regex
                            const regex = /电话号码:\s*(\d+)\s*微信号:\s*(\d+)/;
                            const match = output.match(regex);

                            let phone = null;
                            let wechat = null;

                            if (match) {
                              phone = match[1];
                              wechat = match[2];
                              // Remove the matched part from the original string
                              output = output.replace(regex, "").trim();
                            }

                            console.log("Phone:", phone);
                            console.log("WeChat:", wechat);
                            console.log("Updated Output:", output);

                            if (phone)
                              formdata.append('phone', phone)
                            if (wechat)
                              formdata.append('wechat', wechat)


                            // if (DFPassed && factCheckComment.includes("不匹配")) {
                            //   formdata.append("comment", `${Duplicateresult == "No" ? "" : `是否重复：${Duplicateresult}，匹配度：`}` + result + " " + output  );
                            //   formdata.append("activity_time", activity_time);
                            //   formdata.append("status", "备用人才");
                            // } else if(factCheckComment.includes("不确定")){
                            //   formdata.append("comment", `${Duplicateresult == "No" ? "" : `是否重复：${Duplicateresult}，匹配度：`}` + factCheckComment + " " + output  );
                            //   formdata.append("activity_time", activity_time);
                            //   formdata.append("status", "备用人才");
                            // }else {
                            //   formdata.append("comment", `${Duplicateresult == "No" ? "" : `是否重复：${Duplicateresult}，匹配度：`}` + factCheckComment + " " + output  );
                            //   formdata.append("activity_time", activity_time);
                            //   formdata.append("status", "待联系");
                            // }

                            async function checkUserType(user_id) {
                              const data = new URLSearchParams();
                              data.append('user_id', user_id);
                              const response = await fetch('https://talent.example.invalid/api/get_user_role.php', {
                                method: 'POST',
                                headers: {
                                  'Content-Type': 'application/x-www-form-urlencoded'
                                },
                                body: data
                              });

                              const result = await response.json();
                              return result.type;
                            }
                            const userType = await checkUserType(inchargeID);

                            const recommend = extractProcessedResumeRecommend(processedResume, name);

                            if (userType == "client" || userType == "client admin") {
                              const fields = getClientScreeningResumeFields(factCheckComment, recommend);
                              formdata.append("status", fields.status);
                              formdata.append("comment", fields.comment);
                            }
                            else {
                              formdata.append("comment", `${Duplicateresult == "No" ? "" : `是否重复：${Duplicateresult}，匹配度：`}` + factCheckComment + " " + output);
                              formdata.append("status", "待联系");
                            }

                            const salary = extractProcessedResumeField(processedResume, "期待薪资");
                            if (salary) {
                              formdata.append("salary", salary);
                            }
                            const age = extractProcessedResumeField(processedResume, "年龄");
                            if (age) {
                              formdata.append("age", age);
                            }
                            const location = extractProcessedResumeField(processedResume, "居住地");
                            if (location) {
                              formdata.append("location", location);
                            }

                            if (phone != null) {
                              formdata.append("phone", phone)
                            }
                            if (wechat != null) {
                              formdata.append("wechat", wechat)
                            }
                            formdata.append('source', isElite ? 'liepin_gold' : 'liepin')

                            const requestOptions = {
                              method: "POST",
                              headers: myHeaders,
                              body: formdata,
                              redirect: "follow"
                            };

                            if (shouldSend) {
                              upload_status = "Success"
                              try {
                                const response = await TalentMatchEducation.fetchAddScreeningResume(
                                  "https://talent.example.invalid/api/add_screening_resume.php",
                                  requestOptions,
                                  keywords?.eduInfoContent,
                                  content
                                );
                                const uploadRespText = await response.text();
                                if (!response.ok || uploadRespText.toLowerCase().includes("error")) {
                                  upload_status = "失败";
                                  console.warn("上传失败响应:", uploadRespText);
                                } else {
                                  upload_status = "成功";
                                }
                              } catch {
                                upload_status = "失败"
                              }

                              const formData2 = new URLSearchParams();
                              formData2.append('position_id', positionID);
                              formData2.append('title', "发现匹配人选");
                              const h5Candidate = buildH5CandidateContent(
                                name,
                                String(formdata.get("comment") || factCheckComment || "").trim(),
                                processedResume
                              );
                              console.log("【H5测试】" + h5Candidate.content);
                              formData2.append('content', h5Candidate.content);
                              formData2.append('status', "st1");
                              formData2.append('next_status', "nx st1");
                              formData2.append('custom_fields', "{}");

                              fetch('https://talent.example.invalid/api/add_ai_posts.php', {
                                method: 'POST',
                                headers: {
                                  'Content-Type': 'application/x-www-form-urlencoded',
                                },
                                body: formData2.toString(),
                              })
                              console.log("添加H5 post")
                            } else {
                              console.log("不添加到Anyjob");
                              upload_status = "不需要上传";
                            }
                          } else {
                            console.log(`事实检查不通过`);
                            factCheckResult = responseData
                          }
                        }
                      }

                      // 实时处理结束后，发送简历数据
                      await sendResumeData(
                        content,
                        selectedPositionName,
                        keywords,
                        result,
                        isElite,
                        note,
                        factCheckResult,
                        Duplicateresult,
                        upload_status,
                        activity_time
                      );

                      index++;
                      await clickAndLogNextSpan();
                    } catch (error) {
                      console.error("处理简历数据时出错:", error);
                      index++;
                      await clickAndLogNextSpan();
                    }
                  } else {
                    if (window.TalentMatchLiepinRisk?.isBatchPausedOnVerification?.()) {
                      console.warn("[TalentMatch Liepin] 验证未完成，已停止批量");
                      await notifyBatchTerminal({
                        reason: "verification-required",
                        pauseBatch: true,
                      });
                      return null;
                    }
                    console.log(`结束当前人处理`)
                    index++;
                    await clickAndLogNextSpan()
                    return null
                  }

                }, (window.TalentMatchLiepinRisk?.CONFIG?.clickDelayMs ?? 8000));
              } else {
                await sendResumeData("Done", "", "", "", "", "");

                async function setTitleToCompleted() {
                  // 修改文档的标题为 "已完成"
                  document.title = "已完成";
                  try {
                    await notifyBatchTerminal({
                      status: "completed",
                      reason: "completed",
                    });
                    console.log("[Injected Script] 页面完成消息已发送");
                  } catch (error) {
                    console.error("[Injected Script] 发送页面完成消息失败:", error);
                  }
                }

                // 调用函数
                setTitleToCompleted();
              }
            }

            if (spans.length > 0) {
              clickAndLogNextSpan();
            } else {
              console.error("没有找到任何 .jsx-915804768.c-tab 元素");
              await notifyBatchTerminal({
                reason: "resume-tabs-not-found",
              });
            }
          }
          // 调用 handleBatchSave 开始处理
          console.log("[Injected Script] 准备调用 handleBatchSave 函数，职位名称:", positionName);
          await handleBatchSave(positionName);
          console.log("[Injected Script] handleBatchSave 函数调用完成");
        } catch (error) {
          console.error("[Injected Script] 执行脚本时出错:", error);
          try {
            await notifyBatchTerminal({
              reason: `runtime-error:${error?.message || String(error)}`,
            });
          } catch (notifyError) {
            console.error(
              "[Injected Script] 上报批量页面失败状态时出错:",
              notifyError
            );
          }
        }
      },
      args: [params || {}, runId]
        })
      )
    .then((results) => {
      console.log("[Background] 脚本注入成功，结果:", results);
    }).catch((error) => {
      console.error("[Background] 脚本注入失败:", error);
      enqueueBatchScheduler(() =>
        finishBatchTab(tabId, {
          runId,
          status: `injection-failed:${error?.message || String(error)}`,
        })
      );
    });
  }
}
