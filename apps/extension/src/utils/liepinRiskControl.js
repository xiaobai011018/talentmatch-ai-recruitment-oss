/**
 * 猎聘批量查看简历 — 风控缓解（验证页检测、暂停等待、读取节奏）
 * 注入到 batchshowresume 页面后挂载 window.TalentMatchLiepinRisk
 */
(function initLiepinRiskControl(global) {
  const VERIFICATION_PATTERN =
    /安全验证|人机验证|请完成验证|请先完成|访问过于频繁|滑块验证|完成滑块|captcha|geetest/i;

  const CONFIG = {
    clickDelayMs: 8000,
    iframePollMs: 2500,
    iframeMaxAttempts: 12,
    verificationPollMs: 3000,
    verificationMaxWaitMs: 180000,
    verificationConfirmHits: 2,
    postClickSettleMs: 1200,
  };

  const IFRAME_SELECTOR = 'iframe[src^="/resume/showresumedetail/"]';
  const RESUME_READY_SELECTOR = ".rd-work-info-head";

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function getIframeElement() {
    return document.querySelector(IFRAME_SELECTOR);
  }

  function getIframeDocument() {
    const iframe = getIframeElement();
    if (!iframe) return null;
    try {
      return iframe.contentDocument || iframe.contentWindow?.document || null;
    } catch {
      return null;
    }
  }

  function isVerificationPage(doc) {
    if (!doc?.body) return false;
    if (doc.querySelector(RESUME_READY_SELECTOR)) return false;
    const text = (doc.body.innerText || "").slice(0, 2000);
    return VERIFICATION_PATTERN.test(text);
  }

  function markVerificationTitle() {
    if (!document.title.includes("请完成猎聘验证")) {
      document.title = "【请完成猎聘验证】" + document.title.replace(/^【请完成猎聘验证】/, "");
    }
  }

  function clearVerificationTitle() {
    document.title = document.title.replace(/^【请完成猎聘验证】/, "").trim();
  }

  function isBatchPausedOnVerification() {
    return (
      document.title.includes("请完成猎聘验证") ||
      global.__talentMatchLiepinVerificationPaused === true
    );
  }

  function pauseBatchOnVerification() {
    global.__talentMatchLiepinVerificationPaused = true;
    global.__talentMatchBatchRunning = false;
    markVerificationTitle();
    try {
      chrome?.runtime?.sendMessage?.({ action: "releaseBatchUploadLock" });
    } catch {
      /* 非扩展上下文时忽略 */
    }
  }

  async function waitForVerificationClear(getDoc) {
    let waited = 0;
    let consecutiveVerificationHits = 0;

    while (waited < CONFIG.verificationMaxWaitMs) {
      const doc = typeof getDoc === "function" ? getDoc() : getDoc;
      if (doc && !isVerificationPage(doc) && doc.querySelector(RESUME_READY_SELECTOR)) {
        clearVerificationTitle();
        global.__talentMatchLiepinVerificationPaused = false;
        console.log("[TalentMatch Liepin] 验证已通过，继续处理");
        return true;
      }
      if (doc && isVerificationPage(doc)) {
        consecutiveVerificationHits += 1;
        if (consecutiveVerificationHits >= CONFIG.verificationConfirmHits) {
          markVerificationTitle();
        }
        console.warn(
          "[TalentMatch Liepin] 检测到猎聘验证页，请手动完成验证（等待中）…"
        );
      } else {
        consecutiveVerificationHits = 0;
      }
      await sleep(CONFIG.verificationPollMs);
      waited += CONFIG.verificationPollMs;
    }

    pauseBatchOnVerification();
    console.error("[TalentMatch Liepin] 等待验证超时，已暂停本批次");
    return false;
  }

  async function clickChineseResumeTab(iframeDocument) {
    const spanElements = iframeDocument.querySelectorAll("span.res-tab-title");
    for (const span of spanElements) {
      if (span.textContent.trim() === "中文简历") {
        span.click();
        await sleep(500);
        return true;
      }
    }
    return false;
  }

  async function extractResumeContentFromIframe() {
    if (!getIframeElement()) {
      console.error("[TalentMatch Liepin] 未找到简历 iframe");
      return null;
    }

    let attempt = 0;
    while (attempt < CONFIG.iframeMaxAttempts) {
      attempt += 1;
      const iframeDocument = getIframeDocument();

      if (iframeDocument?.readyState === "complete") {
        if (isVerificationPage(iframeDocument)) {
          const cleared = await waitForVerificationClear(() => getIframeDocument());
          if (!cleared) return null;
          attempt = 0;
          continue;
        }

        await clickChineseResumeTab(iframeDocument);

        const resumeBody = iframeDocument.querySelector("body");
        const workInfoHead = iframeDocument.querySelector(RESUME_READY_SELECTOR);

        if (resumeBody && workInfoHead) {
          let content = resumeBody.textContent.trim();
          const selfAssessmentPosition = content.lastIndexOf("自我评价");
          if (selfAssessmentPosition !== -1) {
            content = content.substring(0, selfAssessmentPosition).trim();
          }
          clearVerificationTitle();
          return content;
        }
      }

      console.log(
        `[TalentMatch Liepin] iframe 未就绪 (${attempt}/${CONFIG.iframeMaxAttempts})`
      );
      await sleep(CONFIG.iframePollMs);
    }

    const doc = getIframeDocument();
    if (doc && isVerificationPage(doc)) {
      pauseBatchOnVerification();
    }
    console.log("[TalentMatch Liepin] iframe 加载超时");
    return null;
  }

  async function ensureBatchStepReady() {
    await sleep(CONFIG.postClickSettleMs);
    const doc = getIframeDocument();
    if (doc && isVerificationPage(doc)) {
      return waitForVerificationClear(() => getIframeDocument());
    }
    return true;
  }

  async function waitForSinglePageReady(
    containerSelector = "#resume-detail-single"
  ) {
    let waited = 0;
    let consecutiveVerificationHits = 0;

    while (waited < CONFIG.verificationMaxWaitMs) {
      if (
        document.querySelector(containerSelector) &&
        document.querySelector(RESUME_READY_SELECTOR)
      ) {
        clearVerificationTitle();
        return true;
      }
      if (isVerificationPage(document)) {
        consecutiveVerificationHits += 1;
        if (consecutiveVerificationHits >= CONFIG.verificationConfirmHits) {
          markVerificationTitle();
        }
        console.warn(
          "[TalentMatch Liepin] 单页简历：检测到验证，请手动完成…"
        );
        await sleep(CONFIG.verificationPollMs);
        waited += CONFIG.verificationPollMs;
        continue;
      }
      consecutiveVerificationHits = 0;
      await sleep(CONFIG.verificationPollMs);
      waited += CONFIG.verificationPollMs;
    }
    return false;
  }

  global.TalentMatchLiepinRisk = {
    CONFIG,
    sleep,
    getIframeElement,
    getIframeDocument,
    isVerificationPage,
    isBatchPausedOnVerification,
    waitForVerificationClear,
    extractResumeContentFromIframe,
    ensureBatchStepReady,
    waitForSinglePageReady,
  };
})(typeof window !== "undefined" ? window : self);
