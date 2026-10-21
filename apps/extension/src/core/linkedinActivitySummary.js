/**
 * LinkedIn Sales Navigator「总结近期动态」批量流程
 * 采集：列表弹层（快）→ 失败则 /in/ 主页（准）；Side Sheet 仅取基本信息
 * 策略：近 30 天内最多 N 条；30 天内无则 fallback 1～2 条历史帖
 */
(function () {
  const STORAGE_KEY = "talentMatchActivitySummaryState";
  const activityBotId = "__TALENTMATCH_MODEL_20__";
  const maxActivityPosts = 6;
  const maxScrapePosts = 12;
  const activityWindowDays = 30;
  const historicalFallbackCount = 2;
  const confirmedNoActivityResult = "近期无公开动态可分析";
  const scrapeFailedResult = "动态采集失败，建议人工查看";
  const restrictedAccessResult = "采集受限（无公开 /in/ 链接），建议人工查看";
  const eachResumeMinimalTime = 8000;
  let activeListPostsTrigger = null;

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function getState() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function setState(state) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function clearState() {
    sessionStorage.removeItem(STORAGE_KEY);
    try {
      chrome.runtime.sendMessage({ action: "talentMatchActivitySummaryDone" });
    } catch (_) {}
  }

  async function sendResumeData(
    content,
    savePositionName,
    linkedinLink,
    result,
    lastLoginDate
  ) {
    const data = {
      positionName: savePositionName,
      detailedResume: content,
      link: linkedinLink,
      result: result,
      lastLoginDate: lastLoginDate || "",
    };

    try {
      const response = await fetch("http://localhost:8000/LinkedInResumeBatchSave/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      const contentType = response.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        throw new Error("服务器返回的不是 JSON 格式的响应");
      }
      const responseData = await response.json();
      console.log("[ActivitySummary] 保存成功:", linkedinLink || content.slice(0, 20));
      return responseData;
    } catch (error) {
      console.error("[ActivitySummary] 保存失败（继续下一项）:", error);
      return null;
    }
  }

  async function sendActivityPromptToAPI(prompt) {
    const formData = new FormData();
    formData.append("chatbotID", activityBotId);
    formData.append("userID", "__TALENTMATCH_USER_01__");
    formData.append("prompt", prompt);
    formData.append("permission", "1");

    const response = await fetch("https://model.example.invalid/api/completions/quora.php", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    const content = result?.choices?.[0]?.message?.content || "";
    if (content) {
      console.log("[ActivitySummary] Bot 返回成功，字数:", content.length);
    }
    return content;
  }

  function extractLastLoginDate(root) {
    let lastLoginDate = "";
    (root || document).querySelectorAll("time").forEach((timeElement) => {
      const textContent = timeElement.textContent || timeElement.innerText;
      if (textContent.includes("ago")) {
        lastLoginDate = textContent.replace(/\n/g, "").replace(/\s{2,}/g, " ").trim();
      }
    });
    return lastLoginDate;
  }

  function extractBasicInfo(leadSideSheet, candidateLink, nameFromList) {
    const nameEl = leadSideSheet.querySelector('[data-anonymize="person-name"]');
    const titleEl = leadSideSheet.querySelector(
      '[data-anonymize="title"], [data-anonymize="job-title"]'
    );
    const companyEl = leadSideSheet.querySelector('[data-anonymize="company-name"]');

    return {
      name: (nameEl?.textContent || nameFromList || "").trim(),
      link: candidateLink,
      title: (titleEl?.textContent || "").trim(),
      company: (companyEl?.textContent || "").trim(),
      lastLoginDate: extractLastLoginDate(leadSideSheet),
    };
  }

  function formatBasicInfo(basic) {
    return [
      `姓名：${basic.name || "未知"}`,
      `链接：${basic.link || "未知"}`,
      `当前公司：${basic.company || "未知"}`,
      `当前职位：${basic.title || "未知"}`,
      `最近登录：${basic.lastLoginDate || "未知"}`,
    ].join("\n");
  }

  function robustClick(element) {
    if (!element) return;
    element.scrollIntoView({ block: "center", inline: "nearest" });
    for (const type of ["pointerdown", "mousedown", "mouseup"]) {
      element.dispatchEvent(
        new MouseEvent(type, { bubbles: true, cancelable: true, view: window })
      );
    }
    if (typeof element.click === "function") {
      element.click();
    } else {
      element.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true, view: window })
      );
    }
  }

  function findRecentPostsTrigger(listElement) {
    if (!listElement) return null;

    const stableTrigger = listElement.querySelector(
      'button[data-control-name="search_spotlight_posted_on_linkedin"]'
    );
    if (stableTrigger) {
      console.log(
        "[ActivitySummary] 通过 data-control-name 找到 recent posts 按钮:",
        stableTrigger.textContent?.replace(/\s+/g, " ").trim()
      );
      return stableTrigger;
    }

    let best = null;
    let bestLen = Infinity;

    const walker = document.createTreeWalker(listElement, NodeFilter.SHOW_TEXT);
    let textNode;
    while ((textNode = walker.nextNode())) {
      const text = (textNode.textContent || "").replace(/\s+/g, " ").trim();
      if (!text) continue;
      if (!/(?:\d+\s+)?recent\s+posts?\s+on\s+LinkedIn/i.test(text)) continue;
      if (text.length > 60 || text.length >= bestLen) continue;

      const el = textNode.parentElement;
      if (!el) continue;
      best =
        el.closest("button, a, [role='button'], [tabindex], span[class*='link']") ||
        el;
      bestLen = text.length;
    }

    if (best) {
      console.log("[ActivitySummary] 找到 recent posts 按钮:", best.textContent?.trim());
    }
    return best;
  }

  function getExpectedRecentPostCount(trigger) {
    const text = (trigger?.textContent || "").replace(/\s+/g, " ").trim();
    const match = text.match(/(\d+)\s+recent\s+posts?\s+on\s+LinkedIn/i);
    return match ? parseInt(match[1], 10) : 0;
  }

  function isVisible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    const style = window.getComputedStyle(el);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      Number(style.opacity) === 0 ||
      el.getAttribute("aria-hidden") === "true"
    ) {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return el.getClientRects().length > 0 && rect.width > 0 && rect.height > 0;
  }

  function findListPostsPanelRoot() {
    const candidates = [];

    const contentContainers = document.querySelectorAll(
      '.ph4.pb4[class*="_content-scroll-container_"]'
    );
    for (const container of contentContainers) {
      if (!isVisible(container)) continue;
      const normalizedText = (container.textContent || "").replace(/\s+/g, " ").trim();
      if (!normalizedText.includes("Posts on LinkedIn in the last 30 days")) continue;
      candidates.push(container);
    }

    if (candidates.length > 0) {
      return candidates[candidates.length - 1];
    }

    for (const heading of document.querySelectorAll("h1, h2, h3, span, strong")) {
      const label = (heading.textContent || "").replace(/\s+/g, " ").trim();
      if (label !== "Posts on LinkedIn in the last 30 days") continue;
      if (!isVisible(heading)) continue;

      let root =
        heading.closest("[role='dialog']") ||
        heading.closest(".artdeco-hoverable-content") ||
        heading.closest(".artdeco-popover") ||
        heading.closest(".artdeco-modal") ||
        heading.parentElement;

      for (let depth = 0; depth < 10 && root; depth++) {
        if (!isVisible(root)) {
          root = root.parentElement;
          continue;
        }
        const items = root.querySelectorAll("li, article");
        if (items.length > 0) {
          candidates.push(root);
          break;
        }
        root = root.parentElement;
      }
    }

    if (candidates.length === 0) return null;
    return candidates[candidates.length - 1];
  }

  async function waitForListPostsPanel(maxWaitMs) {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      const panel = findListPostsPanelRoot();
      if (panel) return panel;
      await sleep(200);
    }
    return null;
  }

  function closeListPostsPanel(trigger = activeListPostsTrigger) {
    const panel = findListPostsPanelRoot();
    const dismissSelectors = [
      'button[data-x--button^="close-spotlight-"]',
      'button[aria-label="Dismiss spotlight popup"]',
      'button[aria-label="Dismiss"]',
      'button[aria-label="Close"]',
      ".artdeco-modal__dismiss",
    ];

    let dismiss = null;
    let scope = panel;
    for (let depth = 0; depth < 6 && scope && !dismiss; depth++) {
      for (const selector of dismissSelectors) {
        const candidate = scope.querySelector(selector);
        if (candidate && isVisible(candidate)) {
          dismiss = candidate;
          break;
        }
      }
      scope = scope.parentElement;
    }

    if (!dismiss) {
      const globalCandidates = document.querySelectorAll(dismissSelectors.join(", "));
      dismiss = Array.from(globalCandidates).find((candidate) => {
        if (!isVisible(candidate)) return false;
        const text = (candidate.textContent || "").replace(/\s+/g, " ").trim();
        return (
          candidate.matches('button[data-x--button^="close-spotlight-"]') ||
          /Dismiss spotlight popup/i.test(text)
        );
      });
    }

    if (dismiss) {
      robustClick(dismiss);
      return "spotlight-dismiss";
    } else if (trigger?.isConnected) {
      robustClick(trigger);
      return "trigger";
    } else {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return "escape";
    }
  }

  async function ensureListPostsPanelClosed(trigger = activeListPostsTrigger) {
    for (let attempt = 0; attempt < 8; attempt++) {
      if (!findListPostsPanelRoot()) {
        if (!trigger || trigger === activeListPostsTrigger) {
          activeListPostsTrigger = null;
        }
        return true;
      }
      const method = closeListPostsPanel(trigger);
      console.log(`[ActivitySummary] 关闭 Posts 弹层，方式=${method}，尝试=${attempt + 1}`);
      await sleep(600);
    }
    const stillOpen = !!findListPostsPanelRoot();
    if (stillOpen) {
      console.error("[ActivitySummary] Posts 弹层关闭失败，为避免串人停止继续采集");
    } else if (!trigger || trigger === activeListPostsTrigger) {
      activeListPostsTrigger = null;
    }
    return !stillOpen;
  }

  async function ensureSideSheetClosed() {
    for (let attempt = 0; attempt < 5; attempt++) {
      const sheet = document.querySelector(".lead-sidesheet.flex.flex-column.full-height");
      if (!sheet || !isVisible(sheet)) return true;
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(400);
    }
    return true;
  }

  async function prepareCandidateUiClean() {
    await ensureListPostsPanelClosed();
    await ensureSideSheetClosed();
  }

  function extractPostOwner(text) {
    const normalized = (text || "").replace(/\s+/g, " ").trim();
    const possessiveMatch = normalized.match(
      /Open panel to view (.+?)[''\u2019]s posted content/i
    );
    if (possessiveMatch) return possessiveMatch[1].trim();
    const postedMatch = normalized.match(/(.+?) posted on LinkedIn/i);
    if (postedMatch) return postedMatch[1].trim();
    const sharedMatch = normalized.match(/^(.+?) shared a post/i);
    if (sharedMatch) return sharedMatch[1].trim();
    return "";
  }

  function normalizeForNameMatch(name) {
    return (name || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function namesMatch(owner, personName) {
    if (!owner || !personName) return false;
    const ownerNorm = normalizeForNameMatch(owner);
    const nameNorm = normalizeForNameMatch(personName);
    if (!ownerNorm || !nameNorm) return false;

    const nameParts = nameNorm.split(/[\s,]+/).filter((part) => part.length > 2);
    if (nameParts.some((part) => ownerNorm.includes(part))) return true;

    const firstPart = nameNorm.split(/[\s,]+/)[0];
    return firstPart.length > 2 && ownerNorm.includes(firstPart);
  }

  function postsLookLikeStalePanel(posts, personName) {
    if (!personName || posts.length === 0) return false;

    const owners = [];
    for (const post of posts) {
      const owner = extractPostOwner(post.text || "");
      if (owner) owners.push(owner);
    }

    // 正文里没有作者信息 → 信任当前行打开的弹层
    if (owners.length === 0) return false;

    // 只要有一条作者匹配当前候选人，就不视为串人
    if (owners.some((owner) => namesMatch(owner, personName))) return false;

    return true;
  }

  function filterPostsForCandidate(posts, personName) {
    if (posts.length === 0) return posts;

    if (postsLookLikeStalePanel(posts, personName)) {
      console.warn(
        `[ActivitySummary] 弹层疑似串人（作者均不匹配 ${personName}），丢弃 ${posts.length} 条`
      );
      return [];
    }

    return posts.slice(0, maxActivityPosts);
  }

  function getPublicInUrl(collected) {
    const fromField = normalizePublicInUrl(collected?.publicInUrl);
    if (fromField) return fromField;
    const urls = [collected?.candidateLink, collected?.basic?.link].filter(Boolean);
    for (const url of urls) {
      const normalized = normalizePublicInUrl(url);
      if (normalized) return normalized;
    }
    return "";
  }

  function resolveEmptyActivityOutcome(hadRecentPostTrigger, rawListCount) {
    if (hadRecentPostTrigger || rawListCount > 0) return scrapeFailedResult;
    return confirmedNoActivityResult;
  }

  async function navigateToActivityProfile(profileUrl, pageLabel) {
    console.log(`[ActivitySummary] 直接导航到${pageLabel}:`, profileUrl);
    try {
      await chrome.runtime.sendMessage({
        action: "talentMatchActivitySummaryProfilePending",
        profileUrl,
      });
    } catch (err) {
      console.warn("[ActivitySummary] 注册详情页续跑失败，仍尝试导航:", err);
    }
    window.location.assign(profileUrl);
  }

  async function scheduleProfilePhase(state, collected, profileUrl) {
    state.phase = "profile";
    state.pendingBasicInfoText = collected.basicInfoText;
    state.pendingCandidateLink = collected.candidateLink;
    state.pendingLastLoginDate = collected.basic.lastLoginDate;
    state.pendingProfileUrl = profileUrl;
    setState(state);
    console.log("[ActivitySummary] 列表无可靠动态，跳转 /in/ 主页采集:", profileUrl);
    await navigateToActivityProfile(profileUrl, " LinkedIn 公开主页");
  }

  function getCandidateKey(element) {
    if (!element) return "";

    const stableLink = element.querySelector(
      'a[href*="/sales/lead/"], a[href*="linkedin.com/in/"], a[href^="/in/"]'
    );
    if (stableLink?.href) {
      return stableLink.href.split("?")[0].split("#")[0];
    }

    const read = (selector) =>
      (element.querySelector(selector)?.textContent || "").replace(/\s+/g, " ").trim();
    const name = read('[data-anonymize="person-name"]');
    const title = read('[data-anonymize="title"], [data-anonymize="job-title"]');
    const company = read('[data-anonymize="company-name"]');
    return [name, title, company].filter(Boolean).join("|");
  }

  function markCandidateProcessed(state, candidateKey) {
    if (!state || !candidateKey) return;
    const processed = new Set(state.processedCandidateKeys || []);
    processed.add(candidateKey);
    state.processedCandidateKeys = Array.from(processed);
    state.elementIndex = state.processedCandidateKeys.length;
  }

  async function finishCandidateAndAdvance(candidateKey) {
    const state = getState();
    if (!state) return;
    markCandidateProcessed(state, candidateKey);
    setState(state);
  }

  async function scrapeListPostsPanel(maxPosts, expectedCount = 0) {
    const panel = await waitForListPostsPanel(8000);
    if (!panel) {
      console.log("[ActivitySummary] 未出现 Posts 弹层");
      return [];
    }
    if (panel.matches?.('.ph4.pb4[class*="_content-scroll-container_"]')) {
      console.log("[ActivitySummary] 通过 content-scroll-container 锁定当前 Posts 弹层");
    }

    const timePattern = /\b(\d+\s*(?:mo|w|d|yr|y|h|m)s?\s+ago)\b/i;

    const targetCount = Math.max(1, Math.min(maxPosts, expectedCount || 1));
    const contentReadyStart = Date.now();
    while (Date.now() - contentReadyStart < 6000) {
      const visibleTimeTexts = new Set();
      panel.querySelectorAll("span, p, time").forEach((node) => {
        const t = (node.textContent || "").replace(/\s+/g, " ").trim();
        if (timePattern.test(t) && t.length < 20) visibleTimeTexts.add(t);
      });
      if (visibleTimeTexts.size >= targetCount) break;
      if (panel.scrollHeight > panel.clientHeight) {
        panel.scrollBy(0, Math.max(240, Math.round(panel.clientHeight * 0.7)));
      }
      await sleep(500);
    }

    await sleep(800);
    const posts = [];
    const seen = new Set();

    const timeNodes = [];
    panel.querySelectorAll("span, p, time, li").forEach((node) => {
      const t = (node.textContent || "").replace(/\s+/g, " ").trim();
      if (timePattern.test(t) && t.length < 20) timeNodes.push(node);
    });

    for (const timeNode of timeNodes) {
      if (posts.length >= maxPosts) break;

      let block =
        timeNode.closest("li") ||
        timeNode.closest("article") ||
        timeNode.parentElement?.parentElement ||
        timeNode.parentElement;
      if (!block) continue;

      let text = (block.textContent || "").replace(/\s+/g, " ").trim();
      if (text.length < 20 || text.length > 1500) continue;

      const timeMatch = text.match(timePattern);
      const time = timeMatch ? timeMatch[1] : "";
      let body = time ? text.replace(timeMatch[0], "").trim() : text;
      body = body
        .replace(/Posts on LinkedIn in the last 30 days/gi, "")
        .replace(/^(Original|Repost)\s*/i, "")
        .trim();
      if (body.length < 12) continue;

      const key = body.slice(0, 80);
      if (seen.has(key)) continue;
      seen.add(key);

      posts.push({
        index: posts.length + 1,
        type: /repost/i.test(text) ? "repost" : "original",
        time,
        text: body.slice(0, 2000),
        hashtags: [],
        url: "",
      });
    }

    if (posts.length === 0) {
      for (const block of panel.querySelectorAll("li, article")) {
        if (posts.length >= maxPosts) break;
        let text = (block.textContent || "").replace(/\s+/g, " ").trim();
        if (text.length < 25 || text.length > 1200) continue;
        const timeMatch = text.match(timePattern);
        if (!timeMatch) continue;
        let body = text.replace(timeMatch[0], "").trim();
        if (body.length < 12) continue;
        const key = body.slice(0, 80);
        if (seen.has(key)) continue;
        seen.add(key);
        posts.push({
          index: posts.length + 1,
          type: /repost/i.test(text) ? "repost" : "original",
          time: timeMatch[1],
          text: body.slice(0, 2000),
          hashtags: [],
          url: "",
        });
      }
    }

    console.log(`[ActivitySummary] 列表弹层采到 ${posts.length} 条动态`);
    if (posts.length > 0) {
      console.log("[ActivitySummary] 动态正文:", JSON.stringify(posts, null, 2));
    }
    return posts.slice(0, maxPosts);
  }

  async function scrapePostsFromListRow(listElement, suppliedTrigger = null) {
    const trigger = suppliedTrigger || findRecentPostsTrigger(listElement);
    if (!trigger) {
      console.log("[ActivitySummary] 本行无 recent posts 按钮");
      return [];
    }

    let lastPosts = [];

    for (let attempt = 0; attempt < 2; attempt++) {
      const priorClosed = await ensureListPostsPanelClosed();
      if (!priorClosed) {
        throw new Error("Posts 弹层无法关闭，已停止以避免采集到上一位候选人的动态");
      }

      if (attempt > 0) {
        console.log("[ActivitySummary] 列表弹层重试采集");
      }

      console.log("[ActivitySummary] 点击 recent posts 按钮");
      activeListPostsTrigger = trigger;
      robustClick(trigger);
      await sleep(attempt === 0 ? 2500 : 3000);

      const expectedCount = getExpectedRecentPostCount(trigger);
      lastPosts = await scrapeListPostsPanel(maxActivityPosts, expectedCount);
      if (lastPosts.length > 0) break;
    }

    const closed = await ensureListPostsPanelClosed(trigger);
    if (!closed) {
      throw new Error("Posts 弹层无法关闭，已停止以避免采集到上一位候选人的动态");
    }
    await sleep(400);
    return lastPosts;
  }

  function findActivityRoot(scope) {
    const root = scope === document ? document : scope;

    if (root === document && /linkedin\.com\/sales\/lead\//i.test(location.href)) {
      const salesLeadPostLists = Array.from(document.querySelectorAll("main ul.mt-3"))
        .filter((list) => isVisible(list) && list.querySelector(":scope > li"))
        .map((list) => {
          const text = (list.textContent || "").replace(/\s+/g, " ").trim();
          const timeMatches = text.match(
            /\b\d+\s*(?:mo|w|d|yr|y|h|m)s?(?:\s+ago)?\b/gi
          );
          return {
            list,
            score: (timeMatches?.length || 0) * 100 + list.querySelectorAll(":scope > li").length,
          };
        })
        .sort((a, b) => b.score - a.score);

      if (salesLeadPostLists.length > 0 && salesLeadPostLists[0].score >= 100) {
        console.log("[ActivitySummary] 通过 main ul.mt-3 找到 Sales Lead Posts 列表");
        return salesLeadPostLists[0].list;
      }

      const salesLeadPostsXPath =
        "/html/body/main/div[1]/div[3]/div/div/div/div/div/section[3]/section[1]/section[1]/div/ul";
      const salesLeadPostsList = document.evaluate(
        salesLeadPostsXPath,
        document,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      ).singleNodeValue;
      if (salesLeadPostsList instanceof HTMLElement && isVisible(salesLeadPostsList)) {
        console.log("[ActivitySummary] 通过 Sales Lead XPath 找到 Posts 列表");
        return salesLeadPostsList;
      }
    }

    const selectors = [
      '[data-sdui-component*="profileCardsActivity"]',
      '[data-view-name="profile-card-recent-activity"]',
      '[data-view-name*="recent-activity"]',
      '[data-view-name*="activity"]',
      "section.pv-recent-activity-section",
      "section.artdeco-card.pv-profile-section",
      "#content_collections",
      ".profile-recent-activity",
    ];
    for (const sel of selectors) {
      const el = root.querySelector(sel);
      if (el) return el;
    }
    for (const heading of root.querySelectorAll("h2, h3")) {
      const text = (heading.textContent || "").trim();
      if (/^Activity$/i.test(text) || /^Recent activity$/i.test(text)) {
        return heading.closest("section") || heading.closest(".artdeco-card") || heading.parentElement;
      }
    }
    return null;
  }

  async function waitForSideSheetReady(leadSideSheet, maxWaitMs) {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      const nameEl = leadSideSheet.querySelector('[data-anonymize="person-name"]');
      const loading = leadSideSheet.querySelector(
        ".artdeco-loader, .artdeco-spinner, .skeleton-loader"
      );
      if (nameEl && nameEl.textContent.trim() && !loading) {
        return true;
      }
      await sleep(500);
    }
    return !!leadSideSheet.querySelector('[data-anonymize="person-name"]');
  }

  function resolveSalesLeadLink(leadSideSheet) {
    const scope = leadSideSheet || document;
    for (const link of scope.querySelectorAll('a[href*="/sales/lead/"]')) {
      if (link.href) return link.href.split("?")[0];
    }
    return "";
  }

  function normalizePublicInUrl(url) {
    if (!url || typeof url !== "string") return "";
    const cleaned = url.split("?")[0].split("#")[0];
    if (/linkedin\.com\/sales\//i.test(cleaned)) return "";
    if (!/linkedin\.com\/in\//i.test(cleaned)) return "";
    return cleaned;
  }

  function resolveCandidateProfileLink(leadSideSheet) {
    const pick = (href) => normalizePublicInUrl(href);

    const menus = document.querySelectorAll(
      '.artdeco-dropdown__content--is-open, div[role="menu"]'
    );
    for (const menu of menus) {
      for (const link of menu.querySelectorAll('a[href*="linkedin.com/in/"]')) {
        const url = pick(link.href);
        if (url) return url;
      }
      for (const link of menu.querySelectorAll("a")) {
        const label = (link.textContent || "").trim().toLowerCase();
        if (
          (label.includes("view profile") || label.includes("view linkedin profile")) &&
          link.href.includes("/in/")
        ) {
          const url = pick(link.href);
          if (url) return url;
        }
      }
    }

    if (leadSideSheet) {
      for (const link of leadSideSheet.querySelectorAll('a[href*="linkedin.com/in/"]')) {
        const url = pick(link.href);
        if (url) return url;
      }
      const openTab = leadSideSheet.querySelector('a[aria-label="Open profile in new tab"]');
      const openTabUrl = pick(openTab?.href);
      if (openTabUrl) return openTabUrl;
    }

    const openTab = document.querySelector('a[aria-label="Open profile in new tab"]');
    const openTabUrl = pick(openTab?.href);
    if (openTabUrl) return openTabUrl;

    return "";
  }

  async function scrollUntilActivityVisible(container, maxAttempts) {
    const isDocument = container === document;
    const scrollableElement = isDocument
      ? document.scrollingElement || document.documentElement
      : container.querySelector('.overflow-y-auto, .scrollable, [style*="overflow"]') ||
        container;

    for (let i = 0; i < maxAttempts; i++) {
      const scope = isDocument ? document : container;
      if (findActivityRoot(scope)) {
        return true;
      }
      if (isDocument) {
        window.scrollBy(0, 900);
      } else {
        scrollableElement.scrollTop += 500;
      }
      await sleep(600);
    }

    const scope = isDocument ? document : container;
    return !!findActivityRoot(scope);
  }

  async function expandTextInItem(item) {
    const expandBtn = item.querySelector('[data-testid="expandable-text-button"]');
    if (!expandBtn) return;
    expandBtn.click();
    await sleep(800);
  }

  function extractPostText(item) {
    const textEl = item.querySelector('[data-testid="expandable-text-box"]');
    if (textEl && textEl.textContent.trim()) {
      return textEl.textContent.trim();
    }
    const feedCard = item.querySelector(
      '[data-urn*="activity"], [data-urn*="share"], .feed-shared-update-v2'
    );
    if (feedCard && feedCard.textContent.trim()) {
      return feedCard.textContent.replace(/\s+/g, " ").trim().slice(0, 2000);
    }
    const raw = item.textContent.replace(/\s+/g, " ").trim();
    return raw.slice(0, 2000);
  }

  async function scrapeActivityPosts(container, maxPosts) {
    const scope = container === document ? document : container;
    const activityRoot = findActivityRoot(scope);
    if (!activityRoot) {
      console.log("[ActivitySummary] 未找到 Activity 区块");
      return [];
    }

    activityRoot.scrollIntoView({ block: "center" });
    await sleep(2000);

    const posts = [];
    const seen = new Set();

    async function collectVisiblePosts() {
      const itemSelectors = [
        'li[role="listitem"]',
        ".feed-shared-update-v2",
        '[data-urn*="activity"]',
        '[data-urn*="share"]',
        ".profile-creator-shared-content__container",
      ];
      const items = activityRoot.matches("ul")
        ? activityRoot.querySelectorAll(":scope > li")
        : activityRoot.querySelectorAll(itemSelectors.join(", "));
      for (const item of items) {
        if (posts.length >= maxPosts) break;

        await expandTextInItem(item);
        const text = extractPostText(item);
        if (!text) continue;

        const linkEl = item.querySelector('a[href*="/feed/update/urn:li:activity:"]');
        const url = linkEl ? linkEl.href : "";
        const dedupeKey = url || text.slice(0, 120);
        if (seen.has(dedupeKey)) continue;
        seen.add(dedupeKey);

        const itemText = item.textContent || "";
        const type = /reposted this/i.test(itemText) ? "repost" : "original";

        let time = "";
        item.querySelectorAll("p, span, time").forEach((el) => {
          const candidate = (el.textContent || "").trim();
          if (/^\d+\s*(mo|w|d|yr|y|h|m)s?(?:\s+ago)?$/i.test(candidate)) {
            time = candidate;
          }
        });

        const hashtags = [];
        item.querySelectorAll('a[href*="/feed/hashtag/"]').forEach((a) => {
          const tag = a.textContent.trim();
          if (tag) hashtags.push(tag);
        });

        posts.push({
          index: posts.length + 1,
          type,
          time,
          text,
          hashtags,
          url,
        });
      }
    }

    await collectVisiblePosts();

    let carouselAttempts = 0;
    while (posts.length < maxPosts && carouselAttempts < 5) {
      const nextBtn = activityRoot.querySelector(
        'button[aria-label="Next"], button.artdeco-carousel__navigation-button--next'
      );
      if (!nextBtn || nextBtn.disabled) break;

      const beforeCount = posts.length;
      nextBtn.click();
      await sleep(1200);
      await collectVisiblePosts();
      if (posts.length === beforeCount) break;
      carouselAttempts++;
    }

    console.log(`[ActivitySummary] 采到 ${posts.length} 条动态`);
    return posts.slice(0, maxPosts);
  }

  function parseRelativeTimeToDays(timeStr) {
    if (!timeStr) return null;
    const normalized = String(timeStr).replace(/\s+/g, " ").trim().toLowerCase();

    const rules = [
      { re: /(\d+(?:\.\d+)?)\s*(?:mo|mos|month|months)\b/, mult: 30 },
      { re: /(\d+(?:\.\d+)?)\s*(?:yr|y)s?\b/, mult: 365 },
      { re: /(\d+(?:\.\d+)?)\s*(?:w|wk|wks|week|weeks)\b/, mult: 7 },
      { re: /(\d+(?:\.\d+)?)\s*(?:d|day|days)\b/, mult: 1 },
      { re: /(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b/, mult: 1 / 24 },
      {
        re: /(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)\b(?!o)/,
        mult: 1 / 1440,
      },
    ];

    for (const { re, mult } of rules) {
      const match = normalized.match(re);
      if (match) return parseFloat(match[1]) * mult;
    }
    return null;
  }

  function extractTimeFromPost(post) {
    const fromTime = parseRelativeTimeToDays(post?.time);
    if (fromTime != null) return fromTime;

    const text = post?.text || "";
    const fromTextMatch = text.match(
      /from\s+(\d+\s*(?:days?|weeks?|months?|years?|hrs?|hours?|mins?|minutes?))\s+ago/i
    );
    if (fromTextMatch) {
      return parseRelativeTimeToDays(fromTextMatch[1] + " ago");
    }

    const agoMatch = text.match(/\b(\d+\s*(?:mo|w|d|yr|y|h|m)s?\s+ago)\b/i);
    if (agoMatch) {
      return parseRelativeTimeToDays(agoMatch[1]);
    }
    return null;
  }

  function formatPostForBot(post) {
    return {
      index: post.index,
      type: post.type,
      time: post.time,
      text: post.text,
      hashtags: post.hashtags,
      url: post.url,
      window: post.window,
      timeAgoDays: post.timeAgoDays != null ? Math.round(post.timeAgoDays) : null,
    };
  }

  function applyActivityWindowPolicy(posts) {
    if (!posts || posts.length === 0) {
      return { posts: [], policy: "none" };
    }

    const enriched = posts.map((post, idx) => ({
      ...post,
      timeAgoDays: extractTimeFromPost(post),
      _originalIndex: idx,
    }));

    const sortByRecency = (a, b) => {
      if (a.timeAgoDays == null && b.timeAgoDays == null) {
        return a._originalIndex - b._originalIndex;
      }
      if (a.timeAgoDays == null) return 1;
      if (b.timeAgoDays == null) return -1;
      return a.timeAgoDays - b.timeAgoDays;
    };

    const sorted = [...enriched].sort(sortByRecency);

    const recent = sorted
      .filter((p) => p.timeAgoDays != null && p.timeAgoDays <= activityWindowDays)
      .slice(0, maxActivityPosts)
      .map((post, idx) => ({
        ...post,
        index: idx + 1,
        window: "recent_30d",
      }));

    if (recent.length > 0) {
      console.log(`[ActivitySummary] 近${activityWindowDays}天动态 ${recent.length} 条`);
      return { posts: recent, policy: "recent" };
    }

    const historical = sorted
      .filter((p) => p.timeAgoDays != null && p.timeAgoDays > activityWindowDays)
      .slice(0, historicalFallbackCount)
      .map((post, idx) => ({
        ...post,
        index: idx + 1,
        window: "historical_fallback",
      }));

    if (historical.length > 0) {
      const oldestDays = Math.round(historical[historical.length - 1].timeAgoDays);
      console.log(
        `[ActivitySummary] 近${activityWindowDays}天无动态，fallback 历史 ${historical.length} 条（约 ${oldestDays} 天前）`
      );
      return { posts: historical, policy: "historical_fallback" };
    }

    const uncertain = sorted.slice(0, maxActivityPosts).map((post, idx) => ({
      ...post,
      index: idx + 1,
      window: "unknown_time",
    }));

    if (uncertain.length > 0) {
      console.log(
        `[ActivitySummary] 无法解析发布时间，按近${activityWindowDays}天来源保留 ${uncertain.length} 条`
      );
      return { posts: uncertain, policy: "recent" };
    }

    return { posts: [], policy: "none" };
  }

  async function buildActivityResult(activityPosts, jobInfo, policy) {
    if (activityPosts.length === 0) {
      return confirmedNoActivityResult;
    }

    const policyNote =
      policy === "historical_fallback"
        ? `候选人近${activityWindowDays}天无公开动态。以下为更早的历史帖子（最多${historicalFallbackCount}条）。请先明确写「近${activityWindowDays}天无动态」，再简要概括历史内容；不要将历史帖当作近期活跃或当前求职意向依据。`
        : `以下为候选人近${activityWindowDays}天内公开动态（最多${maxActivityPosts}条）。请结合岗位总结近期活动主题、与岗位相关性、是否有求职或 active 信号。`;

    const prompt = `岗位信息：${jobInfo}

分析规则：${policyNote}

候选人动态数据：${JSON.stringify(
      activityPosts.map(formatPostForBot),
      null,
      2
    )}`;

    let result = "";
    for (let attempts = 0; attempts < 5; attempts++) {
      try {
        const botResult = await sendActivityPromptToAPI(prompt);
        if (typeof botResult === "string" && botResult.trim()) {
          result = botResult;
          console.log("[ActivitySummary] Bot 总结全文:\n", botResult);
          break;
        }
      } catch (err) {
        console.warn(`[ActivitySummary] Bot 第 ${attempts + 1} 次失败:`, err);
      }
      if (attempts < 4) await sleep(2000);
    }

    return result.trim() || "动态分析失败，请稍后重试";
  }

  async function saveCandidateRecord(collected, state, result) {
    console.log(
      "[ActivitySummary] 写入 Excel:",
      collected.candidateLink,
      "result=",
      (result || "").slice(0, 40)
    );
    return sendResumeData(
      collected.basicInfoText,
      state.effectivePositionName,
      collected.candidateLink,
      result,
      collected.basic.lastLoginDate
    );
  }

  async function waitForSalesSearchList(maxWaitMs) {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      if (
        /linkedin\.com\/sales\/search/i.test(location.href) &&
        getFilteredListElements().length > 0
      ) {
        await sleep(2000);
        return true;
      }
      await sleep(500);
    }
    return false;
  }

  async function waitForProfilePage(maxWaitMs) {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      if (/linkedin\.com\/in\//i.test(location.href)) {
        await sleep(3000);
        return true;
      }
      await sleep(500);
    }
    return false;
  }

  async function waitForSalesLeadPage(maxWaitMs) {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      if (/linkedin\.com\/sales\/lead\//i.test(location.href)) {
        const hasCandidateContent = !!document.querySelector(
          '[data-anonymize="person-name"], main, [role="main"]'
        );
        if (hasCandidateContent) {
          await sleep(2500);
          return true;
        }
      }
      await sleep(400);
    }
    return false;
  }

  function extractSalesLeadFullName() {
    if (!/linkedin\.com\/sales\/lead\//i.test(location.href)) return "";
    const nameXPath =
      "/html/body/main/div[1]/div[3]/div/div/div/div/div/section[1]/section[1]/div[1]/div[2]/h1";
    const xpathName = document.evaluate(
      nameXPath,
      document,
      null,
      XPathResult.FIRST_ORDERED_NODE_TYPE,
      null
    ).singleNodeValue;
    const nameElement =
      (xpathName instanceof HTMLElement && xpathName) || document.querySelector("main h1");
    return (nameElement?.textContent || "").replace(/\s+/g, " ").trim();
  }

  async function fetchFullNameFromSalesLead(listElement, fallbackName) {
    const detailLink = listElement.querySelector('a[href*="/sales/lead/"]');
    if (!detailLink?.href) {
      console.warn("[ActivitySummary] 缩写姓名未找到 Sales Lead 详情链接:", fallbackName);
      return fallbackName;
    }

    detailLink.click();
    if (!(await waitForSalesLeadPage(20000))) {
      console.warn("[ActivitySummary] 缩写姓名进入详情页超时:", fallbackName);
      if (/linkedin\.com\/sales\/lead\//i.test(location.href)) {
        history.back();
        await waitForSalesSearchList(20000);
      }
      return fallbackName;
    }

    const fullName = extractSalesLeadFullName() || fallbackName;
    console.log(`[ActivitySummary] 详情页姓名: ${fallbackName} -> ${fullName}`);
    history.back();
    if (!(await waitForSalesSearchList(20000))) {
      throw new Error("读取完整姓名后返回 Sales 搜索页超时");
    }
    return fullName;
  }

  function getFilteredListElements() {
    const elements = [];
    const seen = new Set();
    const add = (element) => {
      if (!element || seen.has(element)) return;
      if (!element.querySelector('[data-anonymize="person-name"]')) return;
      seen.add(element);
      elements.push(element);
    };

    document
      .querySelectorAll(
        ".artdeco-list__item.pl3.pv3, li.artdeco-list__item, [role='listitem']"
      )
      .forEach(add);

    document.querySelectorAll('[data-anonymize="person-name"]').forEach((nameEl) => {
      add(
        nameEl.closest(
          ".artdeco-list__item, li, [role='listitem'], [data-x-search-result='LEAD']"
        )
      );
    });

    return elements;
  }

  async function scrollListStepForLazyLoad() {
    const elements = getFilteredListElements();
    const lastElement = elements[elements.length - 1];
    if (lastElement) {
      lastElement.scrollIntoView({ block: "end", inline: "nearest" });
    }

    let scrollableDiv = document.querySelector(
      "div.overflow-x-hidden.overflow-y-auto.p4, [data-scrollable='true']"
    );

    if (!scrollableDiv && lastElement) {
      let parent = lastElement.parentElement;
      while (parent && parent !== document.body) {
        const style = window.getComputedStyle(parent);
        if (
          /(auto|scroll)/.test(style.overflowY) &&
          parent.scrollHeight > parent.clientHeight + 20
        ) {
          scrollableDiv = parent;
          break;
        }
        parent = parent.parentElement;
      }
    }

    if (scrollableDiv) {
      scrollableDiv.scrollBy(0, Math.max(500, Math.round(scrollableDiv.clientHeight * 0.75)));
    } else {
      window.scrollBy(0, Math.max(600, Math.round(window.innerHeight * 0.75)));
    }
    await sleep(1200);
  }

  function getCurrentPaginationPage() {
    const active = document.querySelector(
      "ul.artdeco-pagination__pages li.artdeco-pagination__indicator--number.active"
    );
    if (!active) return null;
    const page = parseInt(active.getAttribute("data-test-pagination-page-btn"), 10);
    return Number.isFinite(page) ? page : null;
  }

  function getFirstCandidateName() {
    const first = getFilteredListElements()[0];
    return (
      first?.querySelector('[data-anonymize="person-name"]')?.textContent?.trim() || ""
    );
  }

  async function waitForPageAfterNavigation(beforePage, beforeFirstName, maxWaitMs) {
    const start = Date.now();
    const beforeUrl = location.href;

    while (Date.now() - start < maxWaitMs) {
      const hasList = getFilteredListElements().length > 0;
      const afterPage = getCurrentPaginationPage();
      const pageChanged = beforePage != null && afterPage != null && afterPage !== beforePage;
      const urlChanged = location.href !== beforeUrl;
      const nameChanged =
        !!beforeFirstName && getFirstCandidateName() !== beforeFirstName;

      if (hasList && (pageChanged || urlChanged || nameChanged || beforePage == null)) {
        await sleep(2000);
        if (getFilteredListElements().length > 0) {
          return true;
        }
      }
      await sleep(500);
    }
    return false;
  }

  async function clickNextPageButton() {
    const nextBtn = document.querySelector(".artdeco-pagination__button--next");
    if (nextBtn && !nextBtn.disabled) {
      console.log("[ActivitySummary] 使用 Next 箭头按钮翻页");
      nextBtn.click();
      await sleep(5000);
      return true;
    }
    return false;
  }

  async function goNextPageOrFinish() {
    const paginationContainer = document.querySelector(
      "ul.artdeco-pagination__pages.artdeco-pagination__pages--number"
    );
    const activePageElement = paginationContainer
      ? paginationContainer.querySelector("li.artdeco-pagination__indicator--number.active")
      : null;

    if (!activePageElement) {
      if (await clickNextPageButton()) return true;
      document.title = "已完成";
      clearState();
      return false;
    }

    const currentPage = parseInt(
      activePageElement.getAttribute("data-test-pagination-page-btn"),
      10
    );
    const nextPageLi = Number.isFinite(currentPage)
      ? paginationContainer.querySelector(
          `li[data-test-pagination-page-btn="${currentPage + 1}"]`
        )
      : null;

    if (nextPageLi) {
      nextPageLi.querySelector("button").click();
      await sleep(5000);
      return true;
    }

    const nextAriaBtn = Number.isFinite(currentPage)
      ? document.querySelector(`button[aria-label="Page ${currentPage + 1}"]`)
      : null;
    if (nextAriaBtn) {
      nextAriaBtn.click();
      await sleep(5000);
      return true;
    }

    if (await clickNextPageButton()) return true;

    document.title = "已完成";
    clearState();
    return false;
  }

  function buildCollectedFromListRow(listElement, nameFromList) {
    const titleEl = listElement.querySelector(
      '[data-anonymize="title"], [data-anonymize="job-title"]'
    );
    const companyEl = listElement.querySelector('[data-anonymize="company-name"]');
    const linkElement = listElement.querySelector(
      'a[href*="/sales/lead/"], a[href*="linkedin.com/in/"], a[href^="/in/"]'
    );
    const candidateLink = linkElement?.href
      ? linkElement.href.split("?")[0]
      : `https://www.linkedin.com/sales/search/people#${encodeURIComponent(nameFromList)}`;
    const basic = {
      name: nameFromList,
      link: candidateLink,
      title: (titleEl?.textContent || "").trim(),
      company: (companyEl?.textContent || "").trim(),
      lastLoginDate: extractLastLoginDate(listElement),
    };
    return {
      basic,
      basicInfoText: formatBasicInfo(basic),
      candidateLink,
    };
  }

  async function runProfilePhase() {
    const state = getState();
    if (!state) return;

    console.log("[ActivitySummary] 主页采 Activity:", location.href);
    const detailFullName = extractSalesLeadFullName();
    const detailedResume = detailFullName
      ? state.pendingBasicInfoText.replace(/^姓名：.*$/m, `姓名：${detailFullName}`)
      : state.pendingBasicInfoText;
    if (detailFullName) {
      console.log("[ActivitySummary] Sales Lead 详情页完整姓名:", detailFullName);
    }

    try {
      const foundActivitySection = await scrollUntilActivityVisible(document, 18);
      const activityRoot = findActivityRoot(document);
      const activityPosts = await scrapeActivityPosts(document, maxScrapePosts);
      const jobInfo = state.customJobRequirement || state.selectedPositionKeywords || "";
      const { posts: windowedPosts, policy } = applyActivityWindowPolicy(activityPosts);

      let result;
      if (windowedPosts.length > 0) {
        result = await buildActivityResult(windowedPosts, jobInfo, policy);
      } else if (state.pendingExpectedPostCount > 0) {
        console.log(
          `[ActivitySummary] 列表预期 ${state.pendingExpectedPostCount} 条但不完整，详情页仍未采到动态`
        );
        result = scrapeFailedResult;
      } else if (!foundActivitySection && !activityRoot) {
        console.log("[ActivitySummary] 主页无 Activity 区块，确认无公开动态");
        result = confirmedNoActivityResult;
      } else if (activityPosts.length === 0) {
        console.log("[ActivitySummary] 主页有 Activity 区块但未采到帖子，标记采集失败");
        result = scrapeFailedResult;
      } else {
        console.log("[ActivitySummary] 主页采到帖子但无近期可分析内容");
        result = confirmedNoActivityResult;
      }

      await sendResumeData(
        detailedResume,
        state.effectivePositionName,
        state.pendingCandidateLink,
        result,
        state.pendingLastLoginDate || windowedPosts[0]?.time || ""
      );
    } catch (err) {
      console.error("[ActivitySummary] 主页采集中出错:", err);
      try {
        await sendResumeData(
          detailedResume,
          state.effectivePositionName,
          state.pendingCandidateLink,
          scrapeFailedResult,
          state.pendingLastLoginDate
        );
      } catch (saveErr) {
        console.error("[ActivitySummary] 保存失败:", saveErr);
      }
    } finally {
      const latest = getState() || state;
      latest.phase = "returning";
      markCandidateProcessed(latest, latest.pendingCandidateKey);
      delete latest.pendingCandidateKey;
      delete latest.pendingExpectedPostCount;
      setState(latest);
      history.back();
    }
  }
  async function openSideSheetAndCollectBasic(element) {
    element.scrollIntoView({ block: "nearest" });

    let nameSpan = null;
    for (let _r = 0; _r < 5; _r++) {
      nameSpan = element.querySelector('span[data-anonymize="person-name"]');
      if (nameSpan) break;
      await sleep(1000);
    }
    if (!nameSpan) return null;

    const nameFromList = nameSpan.textContent.trim();
    const nameLink = nameSpan.closest("a[href]");
    if (nameLink?.href && /linkedin\.com\/sales\/lead\//i.test(nameLink.href)) {
      const candidateLink = nameLink.href.split("?")[0];
      const record = buildCollectedFromListRow(element, nameFromList);
      record.candidateLink = candidateLink;
      record.basic.link = candidateLink;
      record.basicInfoText = formatBasicInfo(record.basic);
      record.publicInUrl = "";
      console.log(
        "[ActivitySummary] 姓名链接会进入 Sales Lead 详情页，跳过点击并使用列表信息:",
        candidateLink
      );
      return record;
    }

    nameSpan.click();
    await sleep(eachResumeMinimalTime);

    const leadSideSheet = document.querySelector(
      ".lead-sidesheet.flex.flex-column.full-height"
    );
    if (!leadSideSheet) {
      console.log("[ActivitySummary] 未找到 lead-sidesheet");
      return null;
    }

    await waitForSideSheetReady(leadSideSheet, 12000);

    let publicInUrl = "";
    const actionMenuButton = leadSideSheet.querySelector(
      '[aria-label="Open actions overflow menu"]'
    ) || document.querySelector('[aria-label="Open actions overflow menu"]');

    if (actionMenuButton) {
      actionMenuButton.click();
      await sleep(1200);
      publicInUrl = normalizePublicInUrl(resolveCandidateProfileLink(leadSideSheet));
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(300);
    } else {
      publicInUrl = normalizePublicInUrl(resolveCandidateProfileLink(leadSideSheet));
    }

    let candidateLink = publicInUrl;
    if (!candidateLink || !candidateLink.includes("linkedin.com/in/")) {
      const salesLeadLink = resolveSalesLeadLink(leadSideSheet);
      if (salesLeadLink) {
        candidateLink = salesLeadLink;
        console.log("[ActivitySummary] 使用 sales/lead 链接:", candidateLink);
      }
    }

    if (!candidateLink) {
      candidateLink = `https://www.linkedin.com/sales/search/people#${encodeURIComponent(
        nameFromList
      )}`;
      console.log("[ActivitySummary] 无公开链接，使用列表标识:", candidateLink);
    }

    if (publicInUrl.includes("linkedin.com/in/")) {
      console.log("[ActivitySummary] 保留 /in/ 链接:", publicInUrl);
    }

    const basic = extractBasicInfo(leadSideSheet, candidateLink, nameFromList);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await sleep(300);
    await ensureSideSheetClosed();
    return {
      basic,
      basicInfoText: formatBasicInfo(basic),
      candidateLink,
      publicInUrl: publicInUrl || "",
    };
  }

  async function processCandidateActivity(element, personName, candidateKey, state) {
    await prepareCandidateUiClean();

    const recentPostsTrigger = findRecentPostsTrigger(element);
    const hadRecentPostTrigger = !!recentPostsTrigger;
    const expectedPostCount = getExpectedRecentPostCount(recentPostsTrigger);
    let rawListActivityPosts = await scrapePostsFromListRow(element, recentPostsTrigger);
    let listActivityPosts = filterPostsForCandidate(rawListActivityPosts, personName);

    if (
      rawListActivityPosts.length > 0 &&
      listActivityPosts.length === 0 &&
      hadRecentPostTrigger
    ) {
      console.warn(
        `[ActivitySummary] 弹层疑似串人（${rawListActivityPosts.length} 条），关闭后重试一次`
      );
      await prepareCandidateUiClean();
      rawListActivityPosts = await scrapePostsFromListRow(element, recentPostsTrigger);
      listActivityPosts = filterPostsForCandidate(rawListActivityPosts, personName);
    }

    const jobInfo = state.customJobRequirement || state.selectedPositionKeywords || "";
    const requiredPostCount = Math.min(expectedPostCount, maxActivityPosts);
    const needsFullNameFromDetail = /\.\s*$/.test(personName);
    let resolvedListRecord = null;

    if (
      hadRecentPostTrigger &&
      requiredPostCount > 0 &&
      listActivityPosts.length < requiredPostCount
    ) {
      console.warn(
        `[ActivitySummary] 弹层预期 ${requiredPostCount} 条，仅采到 ${listActivityPosts.length} 条；丢弃弹层结果并进入 Sales Lead 详情页重采`
      );

      const detailLink = element.querySelector('a[href*="/sales/lead/"]');
      if (detailLink?.href) {
        const record = buildCollectedFromListRow(element, personName);
        const detailUrl = new URL(detailLink.href, location.href).href;
        state.phase = "profile";
        state.pendingBasicInfoText = record.basicInfoText;
        state.pendingCandidateLink = record.candidateLink;
        state.pendingLastLoginDate = "";
        state.pendingCandidateKey = candidateKey;
        state.pendingExpectedPostCount = requiredPostCount;
        state.pendingProfileUrl = detailUrl;
        setState(state);

        // 不触发 Sales Navigator 的 openSidesheetOrLink 点击处理器；
        // 直接导航才能保证进入详情页，而不是偶发打开 Side Sheet。
        await navigateToActivityProfile(detailUrl, " Sales Lead 详情页");
        return "profile";
      }

      console.warn("[ActivitySummary] 未找到 Sales Lead 详情链接，无法执行详情页兜底");
      const record = buildCollectedFromListRow(element, personName);
      await saveCandidateRecord(record, state, scrapeFailedResult);
      await finishCandidateAndAdvance(candidateKey);
      return "continue";
    }

    if (needsFullNameFromDetail) {
      resolvedListRecord = buildCollectedFromListRow(element, personName);
      console.log("[ActivitySummary] 列表姓名疑似缩写，进入详情页读取完整姓名:", personName);
      const fullName = await fetchFullNameFromSalesLead(element, personName);
      if (fullName && fullName !== personName) {
        resolvedListRecord.basic.name = fullName;
        resolvedListRecord.basicInfoText = formatBasicInfo(resolvedListRecord.basic);
      }
    }

    if (listActivityPosts.length > 0) {
      const { posts: windowedPosts, policy } = applyActivityWindowPolicy(listActivityPosts);
      if (windowedPosts.length > 0) {
        const record = resolvedListRecord || buildCollectedFromListRow(element, personName);
        if (!record.basic.lastLoginDate && windowedPosts[0]?.time) {
          record.basic.lastLoginDate = windowedPosts[0].time;
          record.basicInfoText = formatBasicInfo(record.basic);
        }
        console.log("[ActivitySummary] 使用列表弹层动态和列表基本信息，不打开候选人详情页");
        const result = await buildActivityResult(windowedPosts, jobInfo, policy);
        await saveCandidateRecord(record, state, result);
        await finishCandidateAndAdvance(candidateKey);
        return "continue";
      }
      console.log("[ActivitySummary] 列表弹层有帖但无近期可分析内容，尝试 /in/ 兜底");
    }

    const record = resolvedListRecord || buildCollectedFromListRow(element, personName);
    const outcome = resolveEmptyActivityOutcome(
      hadRecentPostTrigger,
      rawListActivityPosts.length
    );
    if (hadRecentPostTrigger && rawListActivityPosts.length === 0) {
      console.log("[ActivitySummary] 有 recent posts 按钮但弹层未采到内容");
    } else if (rawListActivityPosts.length > 0 && listActivityPosts.length === 0) {
      console.log("[ActivitySummary] 列表弹层疑似串人，放弃本条弹层数据");
    } else if (!hadRecentPostTrigger) {
      console.log("[ActivitySummary] 列表无 recent posts 按钮");
    }
    console.log("[ActivitySummary] 结果:", outcome);
    await saveCandidateRecord(record, state, outcome);
    await finishCandidateAndAdvance(candidateKey);
    return "continue";
  }

  async function runListPhase(state) {
    if (!/linkedin\.com\/sales\/search/i.test(location.href)) {
      console.warn("[ActivitySummary] 不在 Sales 搜索页，终止");
      clearState();
      return;
    }

    if (state.pendingPageResume) {
      state.pendingPageResume = false;
      state.elementIndex = 0;
      setState(state);
      if (!(await waitForSalesSearchList(20000))) {
        console.error("[ActivitySummary] 续跑时列表加载超时");
        clearState();
        return;
      }
    }

    await sleep(500);

    while (true) {
      // 外层：逐页；内层：逐人。SPA 翻页后在同脚本内等待并继续，不依赖 auto-resume
      let stableScrollAttempts = 0;
      while (true) {
        if (!/linkedin\.com\/sales\/search/i.test(location.href)) {
          console.warn(
            "[ActivitySummary] 处理候选人时意外离开 Sales 搜索页，停止详情页循环并返回搜索页:",
            location.href
          );
          state = getState() || state;
          state.phase = "returning";
          setState(state);
          history.back();
          return;
        }

        const processed = new Set(state.processedCandidateKeys || []);
        let elements = getFilteredListElements();
        let nextCandidate = elements.find((element) => {
          const key = getCandidateKey(element);
          return key && !processed.has(key);
        });

        if (!nextCandidate) {
          const beforeKeys = new Set(elements.map(getCandidateKey).filter(Boolean));
          await scrollListStepForLazyLoad();
          elements = getFilteredListElements();
          nextCandidate = elements.find((element) => {
            const key = getCandidateKey(element);
            return key && !processed.has(key);
          });
          if (nextCandidate) {
            stableScrollAttempts = 0;
            continue;
          }

          const afterKeys = new Set(elements.map(getCandidateKey).filter(Boolean));
          const discoveredNewCandidate = Array.from(afterKeys).some(
            (key) => !beforeKeys.has(key)
          );
          stableScrollAttempts = discoveredNewCandidate ? 0 : stableScrollAttempts + 1;
          console.log(
            `[ActivitySummary] 暂无未处理候选人，滚动确认 ${stableScrollAttempts}/3，当前 DOM ${elements.length} 人，累计已处理 ${processed.size} 人`
          );
          if (stableScrollAttempts >= 3) break;
          continue;
        }

        const element = nextCandidate;
        if (!element || !element.isConnected) {
          await sleep(300);
          continue;
        }

        element.scrollIntoView({ block: "center", inline: "nearest" });
        await sleep(400);
        await prepareCandidateUiClean();

        const personName =
          element.querySelector('[data-anonymize="person-name"]')?.textContent?.trim() ||
          `#${state.elementIndex}`;
        const candidateKey = getCandidateKey(element);
        console.log("[ActivitySummary] 处理候选人:", personName, "key=", candidateKey);

        const processResult = await processCandidateActivity(
          element,
          personName,
          candidateKey,
          state
        );
        if (processResult === "profile") {
          return;
        }
        state = getState() || state;
      }

      const pageBefore = getCurrentPaginationPage();
      const firstNameBefore = getFirstCandidateName();
      state = getState() || state;
      state.phase = "list";
      state.elementIndex = 0;
      state.pendingPageResume = true;
      setState(state);

      const hasNext = await goNextPageOrFinish();
      if (!hasNext) {
        await sendResumeData("Done", "", "", "", "");
        break;
      }

      console.log("[ActivitySummary] 已翻页，等待新页列表加载...");
      const loaded = await waitForPageAfterNavigation(
        pageBefore,
        firstNameBefore,
        25000
      );
      if (!loaded) {
        console.error(
          "[ActivitySummary] 翻页后列表加载超时，保留 pendingPageResume 便于续跑"
        );
        break;
      }

      state = getState() || state;
      state.pendingPageResume = false;
      state.elementIndex = 0;
      setState(state);
      console.log("[ActivitySummary] 新页列表已就绪，继续处理");
    }
  }

  async function runReturningPhase(state) {
    const ok = await waitForSalesSearchList(20000);
    if (!ok) {
      console.error("[ActivitySummary] 返回 Sales 搜索页超时");
      clearState();
      return;
    }
    state.phase = "list";
    setState(state);
    await runListPhase(state);
  }

  async function runActivitySummary() {
    if (window.__talentMatchActivitySummaryRunning) {
      console.warn("[ActivitySummary] 已有任务在运行");
      return;
    }

    const state = getState();
    if (!state) {
      console.warn("[ActivitySummary] 无状态，跳过");
      return;
    }

    console.log(
      "[ActivitySummary] 启动 phase=",
      state.phase,
      "index=",
      state.elementIndex,
      "url=",
      location.href
    );

    window.__talentMatchActivitySummaryRunning = true;
    try {
      if (state.phase === "profile") {
        if (
          !/linkedin\.com\/in\//i.test(location.href) &&
          !/linkedin\.com\/sales\/lead\//i.test(location.href)
        ) {
          await waitForProfilePage(15000);
        }
        await runProfilePhase();
      } else if (state.phase === "returning") {
        await runReturningPhase(state);
      } else {
        state.phase = "list";
        if (!state.elementIndex) state.elementIndex = 0;
        setState(state);
        await runListPhase(state);
      }
    } catch (err) {
      console.error("[ActivitySummary] 运行异常:", err);
      if (/Failed to fetch|保存失败|network/i.test(String(err))) {
        console.warn("[ActivitySummary] 网络/保存异常，保留状态便于刷新后继续");
      } else {
        clearState();
        document.title = "已完成";
      }
    } finally {
      window.__talentMatchActivitySummaryRunning = false;
    }
  }

  window.__talentMatchRunActivitySummary = runActivitySummary;
  window.__talentMatchInitActivitySummary = function (args) {
    const effectivePositionName = args.positionName || "总结近期动态";
    setState({
      phase: "list",
      elementIndex: 0,
      selectedPositionKeywords: args.selectedPositionKeywords || "",
      customJobRequirement: args.customJobRequirement || "",
      effectivePositionName,
      processedCandidateKeys: [],
    });
  };
})();
