document.addEventListener('DOMContentLoaded', () => {

  const CookieBlock = document.getElementById('CookieBlock')
  const SessionBlock = document.getElementById('SessionBlock')
  // ResumeBlock是猎聘用的Session保存的区块，历史遗留命名问题
  const ResumeBlock = document.getElementById('ResumeBlock')
  const LinkedInSessionBlock = document.getElementById('SessionBlockLinkedIn')

  const AnalyzeBlock = document.getElementById('AnalyzeBlock')

  function hide(dom) {
    dom.style.display = 'none'
  }

  function show(dom) {
    dom.style.display = 'block'
  }

  function CookieOnly() {
    AnalyzeBlock.style.display = 'none'
    document.getElementById('toggleButton').click()
    document.getElementById('toggleButton').style.display = 'none'
    detailedResumeHide()
  }

  function listHide() {
    // 如果当前位于list界面那么需要隐藏的按钮 
    hide(ResumeBlock)
    hide(LinkedInSessionBlock)
    hide(SessionBlock)
  }

  function detailedResumeHide() {
    // 详细简历页面隐藏掉一些不需要的按钮
    hide(LinkedInSessionBlock)
    hide(SessionBlock)
    hide(ResumeBlock)
  }
  function detailedResumeHideD() {
    // 详细简历页面数据集版，比猎头版多显示一个保存简历用的按钮
    hide(LinkedInSessionBlock)
    hide(SessionBlock)
  }

  // 以下，list简历
  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
    const currentTabUrl = tabs[0].url;
    if (
      currentTabUrl.includes('h.liepin.com/search/')
    ) {
      // 猎聘
      listHide()
      show(SessionBlock)
    } else if (
      currentTabUrl.includes('linkedin.com/sales/search')
    ) {
      // 领英
      listHide()
      show(LinkedInSessionBlock)
    } else if (
      currentTabUrl.includes('maimai.cn/ent/talents')
    ) {
      // 脉脉
      CookieOnly()
    }
    // 以下，详细简历
    else if (currentTabUrl.includes('h.liepin.com/resume/')) {
      console.log("Mode：猎聘 详细简历")
      detailedResumeHide()
    } else if (
      currentTabUrl.includes('linkedin.com/in') ||
      currentTabUrl.includes('linkedin.com/sales/lead')
    ) {
      console.log("Mode：领英 详细简历")
      detailedResumeHide()
    } else if (
      currentTabUrl.includes('maimai.cn/ent/micro_resume') ||
      currentTabUrl.includes('maimai.cn/profile/detail')
    ) {
      console.log("Mode：脉脉 详细简历")
      detailedResumeHide()
    } else {
      CookieOnly()
      console.log('我不认为它是招聘网站，如果你认为是，那么需要联系开发者')
    }
  });
});
