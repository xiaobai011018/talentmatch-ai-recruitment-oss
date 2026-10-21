(function initClientScreeningResumeFields(global) {
  function getClientScreeningResumeFields(factCheckComment, recommend) {
    if (factCheckComment.includes("不匹配")) {
      return { status: "备用人才", comment: `一般匹配，${recommend}` };
    }
    if (factCheckComment.includes("不确定")) {
      return { status: "待联系", comment: `一般匹配，${recommend}` };
    }
    if (factCheckComment.includes("非常匹配")) {
      return { status: "待联系", comment: `非常匹配，${recommend}` };
    }
    return { status: "待联系", comment: `匹配，${recommend}` };
  }

  global.getClientScreeningResumeFields = getClientScreeningResumeFields;

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { getClientScreeningResumeFields };
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
