(function installQuoraApiGuard(globalScope) {
  "use strict";

  const QUORA_API_URL =
    "https://model.example.invalid/api/completions/quora.php";
  const SILENT_ERROR_CODE = "QUORA_INVALID_API_KEY";
  const DEBUG_MESSAGE = "AI 服务暂时不可用";

  if (
    !globalScope ||
    globalScope.__talentMatchQuoraApiGuardInstalled ||
    typeof globalScope.fetch !== "function"
  ) {
    return;
  }

  globalScope.__talentMatchQuoraApiGuardInstalled = true;

  const originalFetch = globalScope.fetch.bind(globalScope);
  const originalAlert =
    typeof globalScope.alert === "function"
      ? globalScope.alert.bind(globalScope)
      : null;

  class SilentQuoraApiError extends Error {
    constructor() {
      super(SILENT_ERROR_CODE);
      this.name = "SilentQuoraApiError";
      this.code = SILENT_ERROR_CODE;
      this.silent = true;
    }
  }

  function isQuoraApiRequest(input) {
    const requestUrl =
      typeof input === "string" || input instanceof URL
        ? String(input)
        : input?.url;

    if (!requestUrl) return false;

    try {
      const url = new URL(requestUrl, globalScope.location?.href);
      const target = new URL(QUORA_API_URL);
      return (
        url.origin === target.origin &&
        url.pathname === target.pathname
      );
    } catch (_) {
      return requestUrl.startsWith(QUORA_API_URL);
    }
  }

  function isSilentQuoraApiError(value) {
    if (value?.code === SILENT_ERROR_CODE || value?.silent === true) {
      return true;
    }

    try {
      return String(value).includes(SILENT_ERROR_CODE);
    } catch (_) {
      return false;
    }
  }

  globalScope.__talentMatchIsSilentQuoraApiError =
    isSilentQuoraApiError;

  globalScope.fetch = async function guardedFetch(input, init) {
    const response = await originalFetch(input, init);

    if (!isQuoraApiRequest(input) || response.status !== 401) {
      return response;
    }

    let responseBody = "";
    try {
      responseBody = await response.clone().text();
    } catch (_) {
      return response;
    }

    if (!responseBody.toLowerCase().includes("invalid_api_key")) {
      return response;
    }

    console.debug(`[TalentMatch][Quora API] ${DEBUG_MESSAGE}`, {
      status: response.status,
      error: "invalid_api_key",
    });

    // Reject before callers can parse the error response as a successful
    // choices payload. Existing async chains will enter their failure path.
    throw new SilentQuoraApiError();
  };

  if (originalAlert) {
    globalScope.alert = function guardedAlert(message) {
      if (isSilentQuoraApiError(message)) {
        return;
      }
      return originalAlert(message);
    };
  }
})(globalThis);
