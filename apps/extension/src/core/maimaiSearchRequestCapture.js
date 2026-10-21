(() => {
  if (window.__talentMatchMaiMaiSearchHookInstalled) return;
  window.__talentMatchMaiMaiSearchHookInstalled = true;

  const PENDING_SEARCH_STORAGE_KEY = "talentMatchMaiMaiPendingSearch";
  const SEARCH_PATHS = new Set([
    "/api/ent/v3/search/basic",
    "/sdk/jobs/anti_automation/search/basic"
  ]);
  const FILTER_FIELDS = [
    "cities",
    "degrees",
    "positions",
    "professions",
    "provinces",
    "query",
    "schools",
    "sortby",
    "worktimes",
    "worktimes_min",
    "worktimes_max",
    "gender",
    "region_scope",
    "ht_provinces",
    "ht_cities",
    "query_relation",
    "major",
    "only_bachelor_degree",
    "min_only_bachelor_degree",
    "max_only_bachelor_degree",
    "graduation_year",
    "min_age",
    "max_age",
    "expected_min_salary",
    "expected_max_salary",
    "dynamic_valid_days",
    "has_social_relation",
    "company_interaction",
    "uploaded_resume",
    "delivered_or_can_chat",
    "job_hunting_status",
    "exclude_recently_viewed",
    "recently_untouched_valid_days",
    "remark",
    "in_project",
    "is_friend",
    "allcompanies",
    "search_query",
    "is_985",
    "is_211",
    "is_top_500",
    "is_world_500",
    "mapping_pfs",
    "usePfUpdate"
  ];

  function parseJsonBody(body) {
    if (typeof body !== "string" || !body.trim()) return null;
    try {
      return JSON.parse(body);
    } catch (error) {
      return null;
    }
  }

  function isMaiMaiSearch(url, method) {
    try {
      return (
        String(method || "GET").toUpperCase() === "POST" &&
        SEARCH_PATHS.has(new URL(url, location.href).pathname)
      );
    } catch (error) {
      return false;
    }
  }

  function buildReplacementBody(originalBody) {
    let pending = window.__talentMatchMaiMaiPendingSearch;
    if (!pending) {
      try {
        pending = JSON.parse(
          sessionStorage.getItem(PENDING_SEARCH_STORAGE_KEY) || "null"
        );
      } catch (error) {
        pending = null;
      }
    }
    if (pending?.expiresAt && pending.expiresAt < Date.now()) {
      pending = null;
      sessionStorage.removeItem(PENDING_SEARCH_STORAGE_KEY);
    }
    const originalPayload = parseJsonBody(originalBody);
    const desiredPayload = pending?.payload;
    if (
      !pending ||
      !originalPayload?.search ||
      !desiredPayload?.search
    ) {
      return null;
    }

    const mappedFilters = {};
    FILTER_FIELDS.forEach(key => {
      if (
        Object.prototype.hasOwnProperty.call(desiredPayload.search, key)
      ) {
        mappedFilters[key] = desiredPayload.search[key];
      }
    });

    const originalSearch = originalPayload.search;
    const replacementPayload = {
      ...originalPayload,
      search: {
        ...originalSearch,
        ...mappedFilters,
        page: 0,
        paginationParam: {
          ...(originalSearch.paginationParam || {}),
          page: 1
        }
      }
    };

    window.__talentMatchMaiMaiPendingSearch = null;
    sessionStorage.removeItem(PENDING_SEARCH_STORAGE_KEY);
    return {
      body: JSON.stringify(replacementPayload),
      requestId: pending.requestId,
      appliedFilters: mappedFilters
    };
  }

  function reportResult(requestId, response, data, appliedFilters) {
    const errorCode = data?.error_code ?? data?.errno ?? null;
    const status = Number(response.status || 0);
    const httpOk =
      typeof response.ok === "boolean"
        ? response.ok
        : status >= 200 && status < 300;
    window.dispatchEvent(new CustomEvent("TalentMatchMaiMaiSearchResult", {
      detail: {
        requestId,
        ok:
          httpOk &&
          (errorCode === null || String(errorCode) === "0") &&
          !data?.error,
        status,
        errorCode,
        error: data?.error || null,
        detail: data?.detail || null,
        appliedFilters
      }
    }));
  }

  function installFetchHook() {
    if (
      typeof window.fetch !== "function" ||
      window.fetch.__talentMatchMaiMaiSearchHook
    ) {
      return;
    }

    const originalFetch = window.fetch;
    const wrappedFetch = async function (input, init) {
      const url = typeof input === "string" ? input : input?.url || "";
      const method = String(init?.method || input?.method || "GET").toUpperCase();
      let replacement = null;
      let nextInput = input;
      let nextInit = init;

      if (isMaiMaiSearch(url, method)) {
        let originalBody = typeof init?.body === "string" ? init.body : "";
        if (
          !originalBody &&
          typeof Request !== "undefined" &&
          input instanceof Request
        ) {
          originalBody = await input.clone().text().catch(() => "");
        }
        replacement = buildReplacementBody(originalBody);
        if (replacement) {
          if (
            typeof Request !== "undefined" &&
            input instanceof Request &&
            !init?.body
          ) {
            nextInput = new Request(input, { body: replacement.body });
          } else {
            nextInit = { ...(init || {}), body: replacement.body };
          }
          console.log(
            "[TalentMatch] Applied strategy to MaiMai native search request"
          );
        }
      }

      const response = await originalFetch.call(this, nextInput, nextInit);
      if (replacement) {
        response.clone().json()
          .then(data => reportResult(
            replacement.requestId,
            response,
            data,
            replacement.appliedFilters
          ))
          .catch(() => reportResult(
            replacement.requestId,
            response,
            null,
            replacement.appliedFilters
          ));
      }
      return response;
    };
    wrappedFetch.__talentMatchMaiMaiSearchHook = true;
    window.fetch = wrappedFetch;
  }

  function installXhrHook() {
    const proto = XMLHttpRequest.prototype;
    if (proto.send.__talentMatchMaiMaiSearchHook) return;

    const originalOpen = proto.open;
    const originalSend = proto.send;

    proto.open = function (method, url) {
      this.__talentMatchMaiMaiRequest = {
        url: new URL(url, location.href).href,
        method: String(method || "GET").toUpperCase()
      };
      return originalOpen.apply(this, arguments);
    };

    const wrappedSend = function (body) {
      const candidate = this.__talentMatchMaiMaiRequest;
      const replacement =
        candidate && isMaiMaiSearch(candidate.url, candidate.method)
          ? buildReplacementBody(typeof body === "string" ? body : "")
          : null;

      if (replacement) {
        this.addEventListener("load", () => {
          let data = null;
          try {
            data = JSON.parse(this.responseText);
          } catch (error) {
            // The HTTP status is still useful when the response is not JSON.
          }
          reportResult(
            replacement.requestId,
            this,
            data,
            replacement.appliedFilters
          );
        }, { once: true });
        console.log(
          "[TalentMatch] Applied strategy to MaiMai native XHR search request"
        );
      }
      return originalSend.call(this, replacement?.body ?? body);
    };
    wrappedSend.__talentMatchMaiMaiSearchHook = true;
    proto.send = wrappedSend;
  }

  function ensureHooksInstalled() {
    installFetchHook();
    installXhrHook();
  }

  ensureHooksInstalled();
  const watchdog = setInterval(ensureHooksInstalled, 1000);
  window.addEventListener("pagehide", () => clearInterval(watchdog), {
    once: true
  });
  console.log("[TalentMatch] MaiMai native search hook installed");
})();
