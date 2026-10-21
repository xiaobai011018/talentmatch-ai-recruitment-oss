document.addEventListener('DOMContentLoaded', () => {

  const LinkedInSessionBlock = document.getElementById('SessionBlockLinkedIn')

  const BatchAnaLiepin = document.getElementById('LiepinBatchSaveResumeBlock')

  const LiepinMapping = document.getElementById(`LiepinMappingBlock`)
  const CompanyFilter = document.getElementById('LiepinBatchCompanyFilteringDiv')
  const MaiMaiMapping = document.getElementById("MaiMaiSave/UploadDiv")
  const MaiMaiReplyFilterDiv = document.getElementById("MaiMaiReplyFilterDiv")
  const LinkedInReplyFilterDiv = document.getElementById("LinkedinReplyFilterDiv")
  const BossSaveDiv = document.getElementById("BossSaveBlock")
  const MaiMaiUploadBDDiv = document.getElementById("MaiMaiUploadBDDiv")
  const LiepinFirstFilteringBlock = document.getElementById("LiepinFirstFilteringBlock")
  const LinkedInFirstFilteringBlock = document.getElementById("LinkedInFirstFilteringBlock")
  const MaiMaiFirstFilteringBlock = document.getElementById("MaiMaiFirstFilteringBlock")

  function hide(dom) {
    dom.style.display = 'none'
  }

  function show(dom) {
    dom.style.display = 'block'
  }

  function click(dom) {
    dom.click()
  }



  hide(BatchAnaLiepin)
  hide(LinkedInSessionBlock)
  hide(LiepinMapping)
  hide(MaiMaiMapping)
  hide(MaiMaiReplyFilterDiv)
  hide(CompanyFilter)
  hide(LinkedInReplyFilterDiv)
  hide(BossSaveDiv)
  hide(MaiMaiUploadBDDiv)
  hide(LiepinFirstFilteringBlock)
  hide(LinkedInFirstFilteringBlock)
  hide(MaiMaiFirstFilteringBlock)

  hide(document.getElementById(`LinkedInMapping`))


  // 以下，list简历
  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
    const currentTabUrl = tabs[0].url;

    // 在猎聘或领英上
    if ((currentTabUrl.includes("liepin") && !currentTabUrl.includes("www.liepin.com/job/")) || currentTabUrl.includes("linkedin")) {
      setTimeout(() => {
        if (!currentTabUrl.includes("login")) {
          //document.getElementById("CustomJobDescribe").style.display = "block"
        }
        // show(AnalyzeBlock)
        // show(document.getElementById("onlineCookies"))
        
        // hide(document.getElementById("openGetPositionSessionLiepin"))
        // hide(document.getElementById(`fetchResume`))
        // hide(document.getElementById("strategyDropdown"))
        // hide(document.getElementById("upperOption"))
        // hide(document.getElementById("title"))
      }, 500);
    }



    if (currentTabUrl.includes("www.liepin.com/job/")) {
      console.log("Mode：猎聘 职位详情")
      showLiepinJobDetailLayout();
    }
    if (currentTabUrl.includes("sales/search/company")) {
      document.getElementById("Linkedin_Detail_Div").style.display = "block"
    }

    if (
      currentTabUrl.includes('h.liepin.com/search/')
    ) {
      // 猎聘搜索列表页面 - 使用专用布局
      console.log("检测到猎聘搜索页面URL:", currentTabUrl);
      showLiepinSearchPageLayout();
    } 
    else if (
      /www\.liepin\.com\/company-jobs\/\d+/i.test(currentTabUrl)
    ) {
      console.log("Mode：猎聘 公司岗位")
      showLiepinCompanyJobsLayout();
    }
    else if (
      currentTabUrl.includes('liepin.com/resume/batchshowresume?token=batch')
    ) {
      console.log("Mode：猎聘 批量简历")
      showLiepinBatchResumeLayout();
    }
    else if (
      currentTabUrl.includes('linkedin.com/sales/search')
    ) {
      console.log("Mode：LinkedIn 销售搜索页面")
      showLinkedInSalesSearchLayout();
    } else if (
      currentTabUrl.includes(`linkedin.com/talent/hire/`)
    ) {
      console.log("Mode：LinkedIn 招聘搜索页面")
      showLinkedInTalentSearchLayout();
    } else if (
      currentTabUrl.includes(`linkedin.com/talent/search?`)
    ) {
      console.log("Mode：LinkedIn 招聘搜索页面")
      showLinkedInTalentSearchLayout();
    } else if (
      currentTabUrl.includes('maimai.cn/ent/v41/recruit') ||
      currentTabUrl.includes('maimai.cn/ent/talents/discover/search_v2')
    ) {
      console.log("Mode：脉脉 招聘页面")
      showMaiMaiRecruitLayout();
    }
    // 以下，详细简历
    else if (currentTabUrl.includes('h.liepin.com/resume/')) {
      console.log("Mode：猎聘 详细简历")
      showLiepinDetailResumeLayout();
    } else if (
      currentTabUrl.includes('linkedin.com/in') ||
      currentTabUrl.includes('linkedin.com/sales/lead') ||
      currentTabUrl.includes(`linkedin.com/talent/search/profile/`)
    ) {
      console.log("Mode：领英 详细简历")
      showCookieOnlyLayout()
    } else if (
      currentTabUrl.includes(`www.zhipin.com/job_detail/`)
    ) {
      console.log("Mode：BOSS 职位详细")
      showBossJobDetailLayout();
    }else if(
      currentTabUrl.includes(`zhipin.com/web/geek/jobs`) 
     ){
      console.log("Mode：BOSS 求职者岗位页面")
      showBossGeekJobsLayout();
     } 
     else if(
      currentTabUrl.includes(`zhipin.com/gongsi/job/`)
     ){
      console.log("Mode：BOSS 公司岗位页面")
      showBossCompanyJobLayout();
     }
     else if(
      currentTabUrl.includes(`zhipin.com/overseas/`)
     ){
      console.log("Mode：BOSS 海外岗位页面")
      showBossOverseasLayout();
     }
     else if(
      currentTabUrl.includes(`rd6.zhaopin.com/app/search`)
     ){
      console.log("Mode：智联招聘 搜索页面")
      showZhiLianSearchLayout();
     }
     else {
      console.log("Mode：未知页面 - 使用Cookie专用布局")
      showCookieOnlyLayout()
    }
  });
});

// =====================
// 猎聘搜索列表页面专用布局控制
// =====================
function showLiepinSearchPageLayout() {
  console.log("执行猎聘搜索列表页面专用布局");
  
  // 1. 强制显示AnalyzeBlock
  const analyzeBlock = document.getElementById('AnalyzeBlock');
  if (analyzeBlock) {
    analyzeBlock.style.setProperty('display', 'block', 'important');
    console.log("显示AnalyzeBlock");
  }

  // 2. 创建水平布局包装器并显示refreshButtonContainer和LiepinBatchFirstFilteringDiv
  const refreshBtn = analyzeBlock.querySelector('.refreshButtonContainer');
  const batchDiv = document.getElementById('LiepinBatchFirstFilteringDiv');
  
  // 创建水平包装器
  let buttonGroupWrapper = document.getElementById('buttonGroupWrapper');
  if (!buttonGroupWrapper) {
    buttonGroupWrapper = document.createElement('div');
    buttonGroupWrapper.id = 'buttonGroupWrapper';
    buttonGroupWrapper.className = 'button-group-horizontal';
    buttonGroupWrapper.style.setProperty('display', 'flex', 'important');
    buttonGroupWrapper.style.setProperty('position', 'relative', 'important');
    buttonGroupWrapper.style.setProperty('z-index', '1', 'important');
    buttonGroupWrapper.style.setProperty('pointer-events', 'none', 'important');
    buttonGroupWrapper.style.setProperty('gap', '16px', 'important');
    buttonGroupWrapper.style.setProperty('align-items', 'center', 'important');
    buttonGroupWrapper.style.setProperty('justify-content', 'center', 'important');
    // 插入到refreshBtn之前
    if (refreshBtn && refreshBtn.parentElement) {
      refreshBtn.parentElement.insertBefore(buttonGroupWrapper, refreshBtn);
    }
  }
  
  if (buttonGroupWrapper) {
    buttonGroupWrapper.style.setProperty('display', 'flex', 'important');
    console.log("显示buttonGroupWrapper");
  }
  
  if (refreshBtn) {
    refreshBtn.style.setProperty('display', 'flex', 'important');
    refreshBtn.style.setProperty('position', 'relative', 'important');
    refreshBtn.style.setProperty('z-index', '2', 'important');
    refreshBtn.style.setProperty('pointer-events', 'auto', 'important');
    refreshBtn.style.setProperty('margin', '0', 'important');
    refreshBtn.style.setProperty('padding', '0', 'important');
    refreshBtn.style.setProperty('flex', '0 1 auto', 'important');
    // 移动到包装器中
    if (refreshBtn.parentElement !== buttonGroupWrapper) {
      buttonGroupWrapper.appendChild(refreshBtn);
    }
    console.log("显示refreshButtonContainer");
  }
  
  if (batchDiv) {
    batchDiv.style.setProperty('display', 'flex', 'important');
    batchDiv.style.setProperty('position', 'relative', 'important');
    batchDiv.style.setProperty('z-index', '2', 'important');
    batchDiv.style.setProperty('pointer-events', 'auto', 'important');
    batchDiv.style.setProperty('margin', '0', 'important');
    batchDiv.style.setProperty('padding', '0', 'important');
    batchDiv.style.setProperty('flex', '0 1 auto', 'important');
    // 移动到包装器中
    if (batchDiv.parentElement !== buttonGroupWrapper) {
      buttonGroupWrapper.appendChild(batchDiv);
    }
    console.log("显示LiepinBatchFirstFilteringDiv");
  }

  // 4. 强制显示PositionSessionContainer
  const posSession = document.getElementById('PositionSessionContainer');
  if (posSession) {
    posSession.style.setProperty('display', 'flex', 'important');
    posSession.style.setProperty('flex-direction', 'row', 'important');
    posSession.style.setProperty('align-items', 'center', 'important');
    posSession.style.setProperty('justify-content', 'center', 'important');
    posSession.style.setProperty('gap', '16px', 'important');
    posSession.style.setProperty('width', '100%', 'important');
    posSession.style.setProperty('flex-wrap', 'wrap', 'important');
    posSession.style.setProperty('margin', '8px auto', 'important');
    posSession.style.setProperty('position', 'relative', 'important');
    posSession.style.setProperty('z-index', '1', 'important');
    posSession.style.setProperty('pointer-events', 'none', 'important');
    console.log("显示PositionSessionContainer并设置居中对齐");
    
    // 同时显示其子元素
    const openPositionSessionLiepin = document.getElementById('openPositionSessionLiepin');
    if (openPositionSessionLiepin) {
      openPositionSessionLiepin.style.setProperty('display', 'block', 'important');
      openPositionSessionLiepin.style.setProperty('margin', '0', 'important');
      openPositionSessionLiepin.style.setProperty('padding', '12px 20px', 'important');
      openPositionSessionLiepin.style.setProperty('background', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'important');
      openPositionSessionLiepin.style.setProperty('color', 'white', 'important');
      openPositionSessionLiepin.style.setProperty('border', 'none', 'important');
      openPositionSessionLiepin.style.setProperty('border-radius', '12px', 'important');
      openPositionSessionLiepin.style.setProperty('font-size', '1.0em', 'important');
      openPositionSessionLiepin.style.setProperty('font-weight', '500', 'important');
      openPositionSessionLiepin.style.setProperty('cursor', 'pointer', 'important');
      openPositionSessionLiepin.style.setProperty('min-width', '120px', 'important');
      openPositionSessionLiepin.style.setProperty('position', 'relative', 'important');
      openPositionSessionLiepin.style.setProperty('z-index', '2', 'important');
      openPositionSessionLiepin.style.setProperty('pointer-events', 'auto', 'important');
      openPositionSessionLiepin.style.setProperty('flex', '0 1 auto', 'important');
      console.log("显示openPositionSessionLiepin并统一样式");
    }
    
    const LiepinOpenAllBatch = document.getElementById('LiepinOpenAllBatch');
    if (LiepinOpenAllBatch) {
      LiepinOpenAllBatch.style.setProperty('display', 'block', 'important');
      LiepinOpenAllBatch.style.setProperty('position', 'relative', 'important');
      LiepinOpenAllBatch.style.setProperty('z-index', '2', 'important');
      LiepinOpenAllBatch.style.setProperty('pointer-events', 'auto', 'important');
      LiepinOpenAllBatch.style.setProperty('margin', '0', 'important');
      LiepinOpenAllBatch.style.setProperty('flex', '0 1 auto', 'important');
      console.log("显示LiepinOpenAllBatch");
      
      // 为LiepinOpenAllBatchButton设置统一样式
      const LiepinOpenAllBatchButton = document.getElementById('LiepinOpenAllBatchButton');
      if (LiepinOpenAllBatchButton) {
        LiepinOpenAllBatchButton.style.setProperty('margin', '0', 'important');
        LiepinOpenAllBatchButton.style.setProperty('padding', '12px 20px', 'important');
        LiepinOpenAllBatchButton.style.setProperty('background', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'important');
        LiepinOpenAllBatchButton.style.setProperty('color', 'white', 'important');
        LiepinOpenAllBatchButton.style.setProperty('border', 'none', 'important');
        LiepinOpenAllBatchButton.style.setProperty('border-radius', '12px', 'important');
        LiepinOpenAllBatchButton.style.setProperty('font-size', '1.0em', 'important');
        LiepinOpenAllBatchButton.style.setProperty('font-weight', '500', 'important');
        LiepinOpenAllBatchButton.style.setProperty('cursor', 'pointer', 'important');
        LiepinOpenAllBatchButton.style.setProperty('min-width', '120px', 'important');
        console.log("设置LiepinOpenAllBatchButton统一样式");
      }
    }
  }

  // 5. 强制显示currentPosition
  const curPos = document.getElementById('currentPosition');
  if (curPos) {
    curPos.style.setProperty('display', 'block', 'important');
    console.log("显示currentPosition");
  }

  // 6. 强制显示三个dropdown
  ['headhuntersDropdown','positionsDropdown','strategyDropdown'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'block', 'important');
      console.log(`显示${id}`);
    }
  });

  // 7. 强制显示toggleButton
  const toggleBtn = document.getElementById('toggleButton');
  if (toggleBtn) {
    toggleBtn.style.setProperty('display', 'block', 'important');
    console.log("显示toggleButton");
  }

  // 8. 强制显示collapsibleContent（但保持折叠状态）
  const collapsible = document.getElementById('collapsibleContent');
  if (collapsible) {
    collapsible.style.setProperty('display', 'block', 'important');
    collapsible.classList.remove('open');
    console.log("显示collapsibleContent但保持折叠状态");
    
      // 9. 强制显示指定的功能块
  ['LiepinBatchCompanyFilteringDiv','CookieBlock','SessionBlock','LiepinMappingBlock','CustomJobDescribe'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'block', 'important');
      console.log(`显示${id}`);
    }
  });
    
    // 10. 隐藏collapsibleContent下其他div
    Array.from(collapsible.children).forEach(child => {
      if (child.id && !['LiepinBatchCompanyFilteringDiv','CookieBlock','SessionBlock','LiepinMappingBlock','CustomJobDescribe'].includes(child.id)) {
        child.style.setProperty('display', 'none', 'important');
        console.log(`隐藏${child.id}`);
      }
    });
  }

  // 11. 隐藏其他不需要的div
  const hideList = [
    'MaiMaiSave/UploadDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'fetchResume'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  // 12. 额外确保MaiMaiSave/UploadDiv被隐藏（针对特定URL）
  const maiMaiSaveDiv = document.getElementById('MaiMaiSave/UploadDiv');
  if (maiMaiSaveDiv) {
    maiMaiSaveDiv.style.setProperty('display', 'none', 'important');
    maiMaiSaveDiv.style.setProperty('visibility', 'hidden', 'important');
    maiMaiSaveDiv.style.setProperty('opacity', '0', 'important');
    maiMaiSaveDiv.style.setProperty('position', 'absolute', 'important');
    maiMaiSaveDiv.style.setProperty('left', '-9999px', 'important');
    console.log("额外确保MaiMaiSave/UploadDiv被隐藏");
  }

  console.log("猎聘搜索列表页面布局设置完成");
}

// =====================
// 猎聘详细简历页面专用布局控制
// =====================
function showLiepinDetailResumeLayout() {
  console.log("执行猎聘详细简历页面专用布局");
  
  // 1. 强制显示AnalyzeBlock
  const analyzeBlock = document.getElementById('AnalyzeBlock');
  if (analyzeBlock) {
    analyzeBlock.style.setProperty('display', 'block', 'important');
    console.log("显示AnalyzeBlock");
  }

  // 2. 强制显示refreshButtonContainer
  const refreshBtn = analyzeBlock.querySelector('.refreshButtonContainer');
  if (refreshBtn) {
    refreshBtn.style.setProperty('display', 'flex', 'important');
    console.log("显示refreshButtonContainer");
  }

  // 3. 强制显示currentPosition
  const curPos = document.getElementById('currentPosition');
  if (curPos) {
    curPos.style.setProperty('display', 'block', 'important');
    console.log("显示currentPosition");
  }

  // 4. 强制显示三个dropdown
  ['headhuntersDropdown','positionsDropdown','strategyDropdown'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'block', 'important');
      console.log(`显示${id}`);
    }
  });

  // 5. 强制显示fetchResume并确保居中对齐
  const fetchResume = document.getElementById('fetchResume');
  if (fetchResume) {
    fetchResume.style.setProperty('display', 'block', 'important');
    fetchResume.style.setProperty('align-self', 'center', 'important');
    fetchResume.style.setProperty('margin', '0 auto', 'important');
    console.log("显示fetchResume并居中对齐");
  }

  // 6. 强制显示toggleButton
  const toggleBtn = document.getElementById('toggleButton');
  if (toggleBtn) {
    toggleBtn.style.setProperty('display', 'block', 'important');
    console.log("显示toggleButton");
  }

  // 7. 强制显示collapsibleContent（但保持折叠状态）
  const collapsible = document.getElementById('collapsibleContent');
  if (collapsible) {
    collapsible.style.setProperty('display', 'block', 'important');
    collapsible.classList.remove('open');
    console.log("显示collapsibleContent但保持折叠状态");
    
    // 8. 强制显示指定的功能块
    ['CookieBlock','SessionBlock','CustomJobDescribe'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.style.setProperty('display', 'block', 'important');
        console.log(`显示${id}`);
      }
    });
    
    // 9. 隐藏collapsibleContent下其他div
    Array.from(collapsible.children).forEach(child => {
      if (child.id && !['CookieBlock','SessionBlock','CustomJobDescribe'].includes(child.id)) {
        child.style.setProperty('display', 'none', 'important');
        console.log(`隐藏${child.id}`);
      }
    });
  }

  // 10. 隐藏其他不需要的div
  const hideList = [
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  console.log("猎聘详细简历页面布局设置完成");
}

// =====================
// 猎聘批量简历页面专用布局控制
// =====================
function showLiepinBatchResumeLayout() {
  console.log("执行猎聘批量简历页面专用布局");
  
  // 1. 强制显示AnalyzeBlock
  const analyzeBlock = document.getElementById('AnalyzeBlock');
  if (analyzeBlock) {
    analyzeBlock.style.setProperty('display', 'block', 'important');
    console.log("显示AnalyzeBlock");
  }

  // 2. 强制显示refreshButtonContainer
  const refreshBtn = analyzeBlock.querySelector('.refreshButtonContainer');
  if (refreshBtn) {
    refreshBtn.style.setProperty('display', 'flex', 'important');
    console.log("显示refreshButtonContainer");
  }

  // 3. 强制显示currentPosition
  const curPos = document.getElementById('currentPosition');
  if (curPos) {
    curPos.style.setProperty('display', 'block', 'important');
    console.log("显示currentPosition");
  }

  // 4. 强制显示三个dropdown
  ['headhuntersDropdown','positionsDropdown','strategyDropdown'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'block', 'important');
      console.log(`显示${id}`);
    }
  });

  // 5. 强制显示LiepinBatchSaveResumeBlockMainAlternative
  const batchSaveBlock = document.getElementById('LiepinBatchSaveResumeBlockMainAlternative');
  if (batchSaveBlock) {
    batchSaveBlock.style.setProperty('display', 'block', 'important');
    
    // 确保button-group-horizontal包装器正确设置
    const buttonGroup = batchSaveBlock.querySelector('.button-group-horizontal');
    if (buttonGroup) {
      buttonGroup.style.setProperty('display', 'flex', 'important');
      buttonGroup.style.setProperty('position', 'relative', 'important');
      buttonGroup.style.setProperty('z-index', '1', 'important');
      buttonGroup.style.setProperty('pointer-events', 'none', 'important');
      buttonGroup.style.setProperty('gap', '16px', 'important');
      buttonGroup.style.setProperty('align-items', 'center', 'important');
      buttonGroup.style.setProperty('justify-content', 'center', 'important');
      buttonGroup.style.setProperty('flex-wrap', 'wrap', 'important');
      buttonGroup.style.setProperty('width', '100%', 'important');
      buttonGroup.style.setProperty('margin', '8px auto', 'important');
    }
    
    // 确保按钮正确设置
    const buttons = batchSaveBlock.querySelectorAll('button');
    buttons.forEach(button => {
      button.style.setProperty('position', 'relative', 'important');
      button.style.setProperty('z-index', '2', 'important');
      button.style.setProperty('pointer-events', 'auto', 'important');
      button.style.setProperty('margin', '0', 'important');
      button.style.setProperty('flex', '0 1 auto', 'important');
      button.style.setProperty('min-width', '120px', 'important');
      button.style.setProperty('isolation', 'isolate', 'important');
      button.style.setProperty('contain', 'layout', 'important');
    });
    
    // 确保按钮容器正确设置
    const buttonContainers = batchSaveBlock.querySelectorAll('.button-group-horizontal > *');
    buttonContainers.forEach(container => {
      container.style.setProperty('position', 'relative', 'important');
      container.style.setProperty('z-index', '2', 'important');
      container.style.setProperty('pointer-events', 'auto', 'important');
      container.style.setProperty('isolation', 'isolate', 'important');
    });
    
    console.log("显示LiepinBatchSaveResumeBlockMainAlternative并应用button-group-horizontal样式");
  }

  // 6. 强制显示toggleButton
  const toggleBtn = document.getElementById('toggleButton');
  if (toggleBtn) {
    toggleBtn.style.setProperty('display', 'block', 'important');
    console.log("显示toggleButton");
  }

  // 7. 强制显示collapsibleContent（但保持折叠状态）
  const collapsible = document.getElementById('collapsibleContent');
  if (collapsible) {
    collapsible.style.setProperty('display', 'block', 'important');
    collapsible.classList.remove('open');
    console.log("显示collapsibleContent但保持折叠状态");
    
    // 8. 强制显示指定的功能块
    ['CookieBlock','LiepinFirstFilteringBlock','ResumeBlock','CustomJobDescribe'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.style.setProperty('display', 'block', 'important');
        console.log(`显示${id}`);
      }
    });
    
    // 9. 隐藏collapsibleContent下其他div
    Array.from(collapsible.children).forEach(child => {
      if (child.id && !['CookieBlock','LiepinFirstFilteringBlock','ResumeBlock','CustomJobDescribe'].includes(child.id)) {
        child.style.setProperty('display', 'none', 'important');
        console.log(`隐藏${child.id}`);
      }
    });
  }

  // 10. 隐藏其他不需要的div
  const hideList = [
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'MaiMaiSave/UploadDiv',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  console.log("猎聘批量简历页面布局设置完成");
}

// =====================
// 猎聘职位详情页面专用布局控制
// =====================
function showLiepinJobDetailLayout() {
  console.log("执行猎聘职位详情页面专用布局");
  
  // 1. 隐藏所有不需要的元素
  const hideList = [
    'AnalyzeBlock',
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'toggleButton',
    'CookieBlock',
    'CustomJobDescribe',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'ResumeBlock',
    'SessionBlockLinkedIn',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'LinkedInFirstFilteringBlock'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  // 2. 特别处理collapsibleContent，确保完全隐藏且不显示背景
  const collapsibleContent = document.getElementById('collapsibleContent');
  if (collapsibleContent) {
    collapsibleContent.style.setProperty('display', 'none', 'important');
    collapsibleContent.style.setProperty('background', 'transparent', 'important');
    collapsibleContent.style.setProperty('border', 'none', 'important');
    collapsibleContent.style.setProperty('margin', '0', 'important');
    collapsibleContent.style.setProperty('padding', '0', 'important');
    collapsibleContent.classList.remove('open');
    console.log("完全隐藏collapsibleContent并移除所有背景样式");
  }

  // 3. 特别处理CustomJobDescribe，确保它被隐藏
  const customJobDescribe = document.getElementById('CustomJobDescribe');
  if (customJobDescribe) {
    customJobDescribe.style.setProperty('display', 'none', 'important');
    console.log("强制隐藏CustomJobDescribe");
  }

  // 3. 强制显示Liepin_Detail_div
  const liepinDetailDiv = document.getElementById('Liepin_Detail_div');
  if (liepinDetailDiv) {
    liepinDetailDiv.style.setProperty('display', 'block', 'important');
    console.log("显示Liepin_Detail_div");
  }

  // 4. 为Liepin_Detail_div中的h3添加白色样式
  const liepinDetailH3 = liepinDetailDiv ? liepinDetailDiv.querySelector('h3') : null;
  if (liepinDetailH3) {
    liepinDetailH3.classList.add('white-title');
    liepinDetailH3.style.setProperty('color', 'white', 'important');
    console.log("设置Liepin_Detail_div标题为白色");
  }

  console.log("猎聘职位详情页面布局设置完成");
}

// =====================
// 猎聘公司岗位页面专用布局控制
// =====================
function showLiepinCompanyJobsLayout() {
  console.log("执行猎聘公司岗位页面专用布局");

  const hideList = [
    'AnalyzeBlock',
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'toggleButton',
    'collapsibleContent',
    'CookieBlock',
    'CustomJobDescribe',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'ResumeBlock',
    'SessionBlockLinkedIn',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'LinkedInFirstFilteringBlock',
    'ZhiLianSave/UploadDiv'
  ];

  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  const exportDiv = document.getElementById('LiepinCompanyJobsExportDiv');
  if (exportDiv) {
    exportDiv.style.setProperty('display', 'block', 'important');
    console.log("显示LiepinCompanyJobsExportDiv");
  }

  console.log("猎聘公司岗位页面布局设置完成");
}

// =====================
// 脉脉招聘页面专用布局控制
// =====================
function showMaiMaiRecruitLayout() {
  console.log("执行脉脉招聘页面专用布局");
  
  // 1. 强制显示AnalyzeBlock
  const analyzeBlock = document.getElementById('AnalyzeBlock');
  if (analyzeBlock) {
    analyzeBlock.style.setProperty('display', 'block', 'important');
    console.log("显示AnalyzeBlock");
  }

  // 2. 强制显示refreshButtonContainer
  const refreshBtn = analyzeBlock.querySelector('.refreshButtonContainer');
  if (refreshBtn) {
    refreshBtn.style.setProperty('display', 'flex', 'important');
    console.log("显示refreshButtonContainer");
  }

  // 3. 强制显示MaiMaiSave/UploadDiv并设置为垂直布局
  const maiMaiSaveDiv = document.getElementById('MaiMaiSave/UploadDiv');
  if (maiMaiSaveDiv) {
    maiMaiSaveDiv.style.setProperty('display', 'flex', 'important');
    maiMaiSaveDiv.style.setProperty('flex-direction', 'column', 'important');
    maiMaiSaveDiv.style.setProperty('align-items', 'center', 'important');
    maiMaiSaveDiv.style.setProperty('justify-content', 'center', 'important');
    maiMaiSaveDiv.style.setProperty('gap', '8px', 'important');
    console.log("显示MaiMaiSave/UploadDiv并设置为垂直布局");
  }

  // 4. 强制显示currentPosition
  const curPos = document.getElementById('currentPosition');
  if (curPos) {
    curPos.style.setProperty('display', 'block', 'important');
    console.log("显示currentPosition");
  }

  // 5. 强制显示三个dropdown
  ['headhuntersDropdown','positionsDropdown','strategyDropdown'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'block', 'important');
      console.log(`显示${id}`);
    }
  });

  // 6. 重新排列元素顺序：将MaiMaiSave/UploadDiv移动到三个dropdown之后
  if (analyzeBlock && maiMaiSaveDiv) {
    // 获取三个dropdown的最后一个元素
    const strategyDropdown = document.getElementById('strategyDropdown');
    if (strategyDropdown && strategyDropdown.parentNode) {
      // 将MaiMaiSave/UploadDiv插入到strategyDropdown之后
      strategyDropdown.parentNode.insertBefore(maiMaiSaveDiv, strategyDropdown.nextSibling);
      console.log("重新排列布局：MaiMaiSave/UploadDiv移动到三个dropdown之后");
    }
  }

  // 7. 强制显示toggleButton
  const toggleBtn = document.getElementById('toggleButton');
  if (toggleBtn) {
    toggleBtn.style.setProperty('display', 'block', 'important');
    console.log("显示toggleButton");
  }

  // 7. 强制显示collapsibleContent（但保持折叠状态）
  const collapsible = document.getElementById('collapsibleContent');
  if (collapsible) {
    collapsible.style.setProperty('display', 'block', 'important');
    collapsible.classList.remove('open');
    console.log("显示collapsibleContent但保持折叠状态");
    
    // 8. 强制显示指定的功能块
    ['MaiMaiUploadBDDiv','MaiMaiReplyFilterDiv','CookieBlock','MaiMaiFirstFilteringBlock','CustomJobDescribe'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.style.setProperty('display', 'block', 'important');
        console.log(`显示${id}`);
      }
    });
    
    // 9. 隐藏collapsibleContent下其他div
    Array.from(collapsible.children).forEach(child => {
      if (child.id && !['MaiMaiUploadBDDiv','MaiMaiReplyFilterDiv','CookieBlock','MaiMaiFirstFilteringBlock','CustomJobDescribe'].includes(child.id)) {
        child.style.setProperty('display', 'none', 'important');
        console.log(`隐藏${child.id}`);
      }
    });
  }

  // 10. 隐藏其他不需要的div
  const hideList = [
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'ResumeBlock',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'SessionBlockLinkedIn',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'LinkedInFirstFilteringBlock'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  console.log("脉脉招聘页面布局设置完成");
}

// =====================
// BOSS职位详情页面专用布局控制
// =====================
function showBossJobDetailLayout() {
  console.log("执行BOSS职位详情页面专用布局");
  
  // 1. 隐藏所有不需要的元素
  const hideList = [
    'AnalyzeBlock',
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'toggleButton',
    'collapsibleContent',
    'CookieBlock',
    'CustomJobDescribe',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'ResumeBlock',
    'SessionBlockLinkedIn',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'LinkedInFirstFilteringBlock'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  // 2. 强制显示Boss_Detail
  const bossDetail = document.getElementById('Boss_Detail');
  if (bossDetail) {
    bossDetail.style.setProperty('display', 'block', 'important');
    console.log("显示Boss_Detail");
  }

  console.log("BOSS职位详情页面布局设置完成");
}

// =====================
// BOSS求职者岗位页面专用布局控制
// =====================
function showBossGeekJobsLayout() {
  console.log("执行BOSS求职者岗位页面专用布局");
  
  // 1. 隐藏所有不需要的元素
  const hideList = [
    'AnalyzeBlock',
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'toggleButton',
    'collapsibleContent',
    'CookieBlock',
    'CustomJobDescribe',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'ResumeBlock',
    'SessionBlockLinkedIn',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'LinkedInFirstFilteringBlock'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  // 2. 强制显示BossSaveBlock
  const bossSaveBlock = document.getElementById('BossSaveBlock');
  if (bossSaveBlock) {
    bossSaveBlock.style.setProperty('display', 'block', 'important');
    console.log("显示BossSaveBlock");
  }

  // 3. 隐藏不需要的按钮，只显示BossSaveJD
  const bossSaveJDCompany = document.getElementById('BossSaveJD_Company');
  const bossSaveJDOverseas = document.getElementById('BossSaveJD_Overseas');
  
  if (bossSaveJDCompany) {
    bossSaveJDCompany.style.setProperty('display', 'none', 'important');
    console.log("隐藏BossSaveJD_Company");
  }
  
  if (bossSaveJDOverseas) {
    bossSaveJDOverseas.style.setProperty('display', 'none', 'important');
    console.log("隐藏BossSaveJD_Overseas");
  }

  console.log("BOSS求职者岗位页面布局设置完成");
}

// =====================
// BOSS公司岗位页面专用布局控制
// =====================
function showBossCompanyJobLayout() {
  console.log("执行BOSS公司岗位页面专用布局");
  
  // 1. 隐藏所有不需要的元素
  const hideList = [
    'AnalyzeBlock',
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'toggleButton',
    'collapsibleContent',
    'CookieBlock',
    'CustomJobDescribe',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'ResumeBlock',
    'SessionBlockLinkedIn',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'LinkedInFirstFilteringBlock'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  // 2. 强制显示BossSaveBlock
  const bossSaveBlock = document.getElementById('BossSaveBlock');
  if (bossSaveBlock) {
    bossSaveBlock.style.setProperty('display', 'block', 'important');
    console.log("显示BossSaveBlock");
  }

  // 3. 隐藏不需要的按钮，只显示BossSaveJD_Company
  const bossSaveJD = document.getElementById('BossSaveJD');
  const bossSaveJDOverseas = document.getElementById('BossSaveJD_Overseas');
  
  if (bossSaveJD) {
    bossSaveJD.style.setProperty('display', 'none', 'important');
    console.log("隐藏BossSaveJD");
  }
  
  if (bossSaveJDOverseas) {
    bossSaveJDOverseas.style.setProperty('display', 'none', 'important');
    console.log("隐藏BossSaveJD_Overseas");
  }

  console.log("BOSS公司岗位页面布局设置完成");
}

// =====================
// BOSS海外岗位页面专用布局控制
// =====================
function showBossOverseasLayout() {
  console.log("执行BOSS海外岗位页面专用布局");
  
  // 1. 隐藏所有不需要的元素
  const hideList = [
    'AnalyzeBlock',
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'toggleButton',
    'collapsibleContent',
    'CookieBlock',
    'CustomJobDescribe',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'ResumeBlock',
    'SessionBlockLinkedIn',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'LinkedInFirstFilteringBlock'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  // 2. 强制显示BossSaveBlock
  const bossSaveBlock = document.getElementById('BossSaveBlock');
  if (bossSaveBlock) {
    bossSaveBlock.style.setProperty('display', 'block', 'important');
    console.log("显示BossSaveBlock");
  }

  // 3. 隐藏不需要的按钮，只显示BossSaveJD_Overseas
  const bossSaveJD = document.getElementById('BossSaveJD');
  const bossSaveJDCompany = document.getElementById('BossSaveJD_Company');
  
  if (bossSaveJD) {
    bossSaveJD.style.setProperty('display', 'none', 'important');
    console.log("隐藏BossSaveJD");
  }
  
  if (bossSaveJDCompany) {
    bossSaveJDCompany.style.setProperty('display', 'none', 'important');
    console.log("隐藏BossSaveJD_Company");
  }

  console.log("BOSS海外岗位页面布局设置完成");
}

// =====================
// LinkedIn销售搜索页面专用布局控制
// =====================
function showLinkedInSalesSearchLayout() {
  console.log("执行LinkedIn销售搜索页面专用布局");
  
  // 1. 强制显示AnalyzeBlock
  const analyzeBlock = document.getElementById('AnalyzeBlock');
  if (analyzeBlock) {
    analyzeBlock.style.setProperty('display', 'block', 'important');
    console.log("显示AnalyzeBlock");
  }

  // 2. 创建水平布局包装器并显示refreshButtonContainer和openPositionSessionLinkedIn
  const refreshBtn = analyzeBlock.querySelector('.refreshButtonContainer');
  const openPositionSessionLinkedIn = document.getElementById('openPositionSessionLinkedIn');
  
  // 创建水平包装器
  let buttonGroupWrapper = document.getElementById('buttonGroupWrapper');
  if (!buttonGroupWrapper) {
    buttonGroupWrapper = document.createElement('div');
    buttonGroupWrapper.id = 'buttonGroupWrapper';
    buttonGroupWrapper.className = 'button-group-horizontal';
    // 插入到refreshBtn之前
    if (refreshBtn && refreshBtn.parentElement) {
      refreshBtn.parentElement.insertBefore(buttonGroupWrapper, refreshBtn);
    }
  }
  
  if (buttonGroupWrapper) {
    buttonGroupWrapper.style.setProperty('display', 'flex', 'important');
    buttonGroupWrapper.style.setProperty('flex-direction', 'row', 'important');
    buttonGroupWrapper.style.setProperty('align-items', 'center', 'important');
    buttonGroupWrapper.style.setProperty('justify-content', 'center', 'important');
    buttonGroupWrapper.style.setProperty('gap', '24px', 'important');
    buttonGroupWrapper.style.setProperty('width', '100%', 'important');
    buttonGroupWrapper.style.setProperty('flex-wrap', 'wrap', 'important');
    buttonGroupWrapper.style.setProperty('margin', '8px auto', 'important');
    buttonGroupWrapper.style.setProperty('position', 'relative', 'important');
    buttonGroupWrapper.style.setProperty('z-index', '1', 'important');
    buttonGroupWrapper.style.setProperty('pointer-events', 'none', 'important');
    console.log("显示buttonGroupWrapper并设置居中对齐");
  }
  
  if (refreshBtn) {
    refreshBtn.style.setProperty('display', 'flex', 'important');
    refreshBtn.style.setProperty('margin', '0', 'important');
    refreshBtn.style.setProperty('padding', '0', 'important');
    refreshBtn.style.setProperty('position', 'relative', 'important');
    refreshBtn.style.setProperty('z-index', '2', 'important');
    refreshBtn.style.setProperty('pointer-events', 'auto', 'important');
    refreshBtn.style.setProperty('flex', '0 1 auto', 'important');
    // 移动到包装器中
    if (refreshBtn.parentElement !== buttonGroupWrapper) {
      buttonGroupWrapper.appendChild(refreshBtn);
    }
    console.log("显示refreshButtonContainer并统一样式");
  }
  
  if (openPositionSessionLinkedIn) {
    openPositionSessionLinkedIn.style.setProperty('display', 'block', 'important');
    openPositionSessionLinkedIn.style.setProperty('margin', '0', 'important');
    openPositionSessionLinkedIn.style.setProperty('padding', '12px 20px', 'important');
    openPositionSessionLinkedIn.style.setProperty('background', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'important');
    openPositionSessionLinkedIn.style.setProperty('color', 'white', 'important');
    openPositionSessionLinkedIn.style.setProperty('border', 'none', 'important');
    openPositionSessionLinkedIn.style.setProperty('border-radius', '12px', 'important');
    openPositionSessionLinkedIn.style.setProperty('font-size', '1.0em', 'important');
    openPositionSessionLinkedIn.style.setProperty('font-weight', '500', 'important');
    openPositionSessionLinkedIn.style.setProperty('cursor', 'pointer', 'important');
    openPositionSessionLinkedIn.style.setProperty('min-width', '120px', 'important');
    openPositionSessionLinkedIn.style.setProperty('position', 'relative', 'important');
    openPositionSessionLinkedIn.style.setProperty('z-index', '2', 'important');
    openPositionSessionLinkedIn.style.setProperty('pointer-events', 'auto', 'important');
    // 移动到包装器中
    if (openPositionSessionLinkedIn.parentElement !== buttonGroupWrapper) {
      buttonGroupWrapper.appendChild(openPositionSessionLinkedIn);
    }
    console.log("显示openPositionSessionLinkedIn并统一样式");
  }

  // 3. 创建水平布局包装器并显示LinkedInMappingButtonHuarenOnlyUpload和LinkedInMappingButtonUnviewedUpload
  const linkedInMappingButtonHuarenOnlyUpload = document.getElementById('LinkedInMappingButtonHuarenOnlyUpload');
  const linkedInMappingButtonUnviewedUpload = document.getElementById('LinkedInMappingButtonUnviewedUpload');
  
  // 创建LinkedIn按钮水平包装器
  let linkedInButtonWrapper = document.getElementById('linkedInButtonWrapper');
  if (!linkedInButtonWrapper) {
    linkedInButtonWrapper = document.createElement('div');
    linkedInButtonWrapper.id = 'linkedInButtonWrapper';
    linkedInButtonWrapper.className = 'button-group-horizontal';
    // 插入到currentPosition之前
    const curPos = document.getElementById('currentPosition');
    if (curPos && curPos.parentElement) {
      curPos.parentElement.insertBefore(linkedInButtonWrapper, curPos);
    }
  }
  
  if (linkedInButtonWrapper) {
    linkedInButtonWrapper.style.setProperty('display', 'flex', 'important');
    linkedInButtonWrapper.style.setProperty('flex-direction', 'row', 'important');
    linkedInButtonWrapper.style.setProperty('align-items', 'center', 'important');
    linkedInButtonWrapper.style.setProperty('justify-content', 'center', 'important');
    linkedInButtonWrapper.style.setProperty('gap', '16px', 'important');
    linkedInButtonWrapper.style.setProperty('width', '100%', 'important');
    linkedInButtonWrapper.style.setProperty('flex-wrap', 'wrap', 'important');
    linkedInButtonWrapper.style.setProperty('margin', '8px auto', 'important');
    linkedInButtonWrapper.style.setProperty('position', 'relative', 'important');
    linkedInButtonWrapper.style.setProperty('z-index', '1', 'important');
    linkedInButtonWrapper.style.setProperty('pointer-events', 'none', 'important');
    console.log("显示linkedInButtonWrapper并设置居中对齐");
  }
  
  if (linkedInMappingButtonHuarenOnlyUpload) {
    linkedInMappingButtonHuarenOnlyUpload.style.setProperty('display', 'block', 'important');
    linkedInMappingButtonHuarenOnlyUpload.style.setProperty('position', 'relative', 'important');
    linkedInMappingButtonHuarenOnlyUpload.style.setProperty('z-index', '2', 'important');
    linkedInMappingButtonHuarenOnlyUpload.style.setProperty('pointer-events', 'auto', 'important');
    linkedInMappingButtonHuarenOnlyUpload.style.setProperty('margin', '0', 'important');
    linkedInMappingButtonHuarenOnlyUpload.style.setProperty('flex', '0 1 auto', 'important');
    // 移动到包装器中
    if (linkedInMappingButtonHuarenOnlyUpload.parentElement !== linkedInButtonWrapper) {
      linkedInButtonWrapper.appendChild(linkedInMappingButtonHuarenOnlyUpload);
    }
    console.log("显示LinkedInMappingButtonHuarenOnlyUpload");
  }
  
  if (linkedInMappingButtonUnviewedUpload) {
    linkedInMappingButtonUnviewedUpload.style.setProperty('display', 'block', 'important');
    linkedInMappingButtonUnviewedUpload.style.setProperty('position', 'relative', 'important');
    linkedInMappingButtonUnviewedUpload.style.setProperty('z-index', '2', 'important');
    linkedInMappingButtonUnviewedUpload.style.setProperty('pointer-events', 'auto', 'important');
    linkedInMappingButtonUnviewedUpload.style.setProperty('margin', '0', 'important');
    linkedInMappingButtonUnviewedUpload.style.setProperty('flex', '0 1 auto', 'important');
    // 移动到包装器中
    if (linkedInMappingButtonUnviewedUpload.parentElement !== linkedInButtonWrapper) {
      linkedInButtonWrapper.appendChild(linkedInMappingButtonUnviewedUpload);
    }
    console.log("显示LinkedInMappingButtonUnviewedUpload");
  }

  // 5. 强制显示currentPosition
  const curPos = document.getElementById('currentPosition');
  if (curPos) {
    curPos.style.setProperty('display', 'block', 'important');
    console.log("显示currentPosition");
  }

  // 6. 强制显示三个dropdown
  ['headhuntersDropdown','positionsDropdown','strategyDropdown'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'block', 'important');
      console.log(`显示${id}`);
    }
  });

  // 7. 强制显示toggleButton
  const toggleBtn = document.getElementById('toggleButton');
  if (toggleBtn) {
    toggleBtn.style.setProperty('display', 'block', 'important');
    console.log("显示toggleButton");
  }

  // 8. 强制显示collapsibleContent（但保持折叠状态）
  const collapsible = document.getElementById('collapsibleContent');
  if (collapsible) {
    collapsible.style.setProperty('display', 'block', 'important');
    collapsible.classList.remove('open');
    console.log("显示collapsibleContent但保持折叠状态");
    
    // 9. 强制显示指定的功能块
    ['LinkedInMappingAll','CookieBlock','LinkedInFirstFilteringBlock','SessionBlockLinkedIn','CustomJobDescribe'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.style.setProperty('display', 'block', 'important');
        console.log(`显示${id}`);
      }
    });
    
    // 10. 隐藏collapsibleContent下其他div
    Array.from(collapsible.children).forEach(child => {
      if (child.id && !['LinkedInMappingAll','CookieBlock','LinkedInFirstFilteringBlock','SessionBlockLinkedIn','CustomJobDescribe'].includes(child.id)) {
        child.style.setProperty('display', 'none', 'important');
        console.log(`隐藏${child.id}`);
      }
    });
    
    // 11. 特别处理LinkedInMappingAll内部的布局
    const linkedInMappingAll = document.getElementById('LinkedInMappingAll');
    if (linkedInMappingAll) {
      // 设置LinkedInMappingAll为垂直布局并居中对齐
      linkedInMappingAll.style.setProperty('display', 'flex', 'important');
      linkedInMappingAll.style.setProperty('flex-direction', 'column', 'important');
      linkedInMappingAll.style.setProperty('align-items', 'center', 'important');
      linkedInMappingAll.style.setProperty('justify-content', 'center', 'important');
      linkedInMappingAll.style.setProperty('gap', '8px', 'important');
      console.log("设置LinkedInMappingAll为垂直居中布局");
      
      // 确保LinkedinReplyFilterDiv正确显示
      const linkedinReplyFilterDiv = linkedInMappingAll.querySelector('#LinkedinReplyFilterDiv');
      if (linkedinReplyFilterDiv) {
        linkedinReplyFilterDiv.style.setProperty('display', 'block', 'important');
        console.log("确保LinkedinReplyFilterDiv正确显示");
      }
      

      
      // 确保所有按钮居中对齐
      const buttons = linkedInMappingAll.querySelectorAll('button');
      buttons.forEach(button => {
        button.style.setProperty('align-self', 'center', 'important');
        button.style.setProperty('margin', '4px auto', 'important');
      });
      console.log("设置LinkedInMappingAll内所有按钮居中对齐");
    }
  }

  // 11. 隐藏其他不需要的div
  const hideList = [
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'fetchResume',
    'LiepinBatchFirstFilteringDiv',
    'ResumeBlock',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  console.log("LinkedIn销售搜索页面布局设置完成");
}

// =====================
// LinkedIn招聘搜索页面专用布局控制
// =====================
function showLinkedInTalentSearchLayout() {
  console.log("执行LinkedIn招聘搜索页面专用布局");
  
  // 1. 强制显示AnalyzeBlock
  const analyzeBlock = document.getElementById('AnalyzeBlock');
  if (analyzeBlock) {
    analyzeBlock.style.setProperty('display', 'block', 'important');
    console.log("显示AnalyzeBlock");
  }

  // 2. 强制显示refreshButtonContainer
  const refreshBtn = analyzeBlock.querySelector('.refreshButtonContainer');
  if (refreshBtn) {
    refreshBtn.style.setProperty('display', 'flex', 'important');
    console.log("显示refreshButtonContainer");
  }

  // 3. 强制显示LinkedInMapping_talent_hire并设置为水平布局
  const linkedInMappingTalentHire = document.getElementById('LinkedInMapping_talent_hire');
  if (linkedInMappingTalentHire) {
    linkedInMappingTalentHire.style.setProperty('display', 'flex', 'important');
    linkedInMappingTalentHire.style.setProperty('flex-direction', 'row', 'important');
    linkedInMappingTalentHire.style.setProperty('align-items', 'center', 'important');
    linkedInMappingTalentHire.style.setProperty('justify-content', 'center', 'important');
    linkedInMappingTalentHire.style.setProperty('gap', '12px', 'important');
    linkedInMappingTalentHire.style.setProperty('width', '100%', 'important');
    linkedInMappingTalentHire.style.setProperty('flex-wrap', 'wrap', 'important');
    linkedInMappingTalentHire.style.setProperty('margin', '8px auto', 'important');
    console.log("显示LinkedInMapping_talent_hire并设置为水平布局");
    
    // 特别处理LinkedInMapping_talent_hire内部的布局
    // 设置所有h3标题的margin为0
    const h3Elements = linkedInMappingTalentHire.querySelectorAll('h3');
    h3Elements.forEach(h3 => {
      h3.style.setProperty('margin', '0', 'important');
      h3.style.setProperty('padding', '0', 'important');
    });
    
    // 设置所有按钮的margin为0
    const buttons = linkedInMappingTalentHire.querySelectorAll('button');
    buttons.forEach(button => {
      button.style.setProperty('margin', '0', 'important');
      button.style.setProperty('padding', '12px 20px', 'important');
    });
    
    console.log("设置LinkedInMapping_talent_hire内部元素样式");
  }

  // 4. 重新排列元素顺序：将LinkedInMapping_talent_hire移动到currentPosition之前
  const curPos = document.getElementById('currentPosition');
  if (analyzeBlock && linkedInMappingTalentHire && curPos) {
    // 将LinkedInMapping_talent_hire插入到currentPosition之前
    if (curPos.parentNode) {
      curPos.parentNode.insertBefore(linkedInMappingTalentHire, curPos);
      console.log("重新排列布局：LinkedInMapping_talent_hire移动到currentPosition之前");
    }
  }

  // 5. 强制显示currentPosition
  if (curPos) {
    curPos.style.setProperty('display', 'block', 'important');
    console.log("显示currentPosition");
  }

  // 6. 强制显示三个dropdown
  ['headhuntersDropdown','positionsDropdown','strategyDropdown'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'block', 'important');
      console.log(`显示${id}`);
    }
  });

  // 7. 强制显示toggleButton
  const toggleBtn = document.getElementById('toggleButton');
  if (toggleBtn) {
    toggleBtn.style.setProperty('display', 'block', 'important');
    console.log("显示toggleButton");
  }

  // 8. 强制显示collapsibleContent（但保持折叠状态）
  const collapsible = document.getElementById('collapsibleContent');
  if (collapsible) {
    collapsible.style.setProperty('display', 'block', 'important');
    collapsible.classList.remove('open');
    console.log("显示collapsibleContent但保持折叠状态");
    
    // 9. 强制显示指定的功能块
    ['CustomJobDescribe'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.style.setProperty('display', 'block', 'important');
        console.log(`显示${id}`);
      }
    });
    
    // 10. 隐藏collapsibleContent下其他div
    Array.from(collapsible.children).forEach(child => {
      if (child.id && !['CustomJobDescribe'].includes(child.id)) {
        child.style.setProperty('display', 'none', 'important');
        console.log(`隐藏${child.id}`);
      }
    });
  }

  // 11. 隐藏其他不需要的div
  const hideList = [
    'PositionSessionContainer',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'fetchResume',
    'LiepinBatchFirstFilteringDiv',
    'ResumeBlock',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInFirstFilteringBlock',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'CookieBlock',
    'SessionBlockLinkedIn'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  console.log("LinkedIn招聘搜索页面布局设置完成");
}

// =====================
// Cookie专用布局控制 - 只显示CookieBlock
// =====================
function showCookieOnlyLayout() {
  console.log("=== 开始执行Cookie专用布局 ===");
  console.log("执行Cookie专用布局 - 只显示CookieBlock");
  
  // 1. 隐藏AnalyzeBlock
  const analyzeBlock = document.getElementById('AnalyzeBlock');
  if (analyzeBlock) {
    analyzeBlock.style.setProperty('display', 'none', 'important');
    console.log("隐藏AnalyzeBlock");
  }

  // 2. 隐藏toggleButton
  const toggleBtn = document.getElementById('toggleButton');
  if (toggleBtn) {
    toggleBtn.style.setProperty('display', 'none', 'important');
    console.log("隐藏toggleButton");
  }

  // 3. 显示collapsibleContent但只显示CookieBlock
  const collapsibleContent = document.getElementById('collapsibleContent');
  if (collapsibleContent) {
    collapsibleContent.style.setProperty('display', 'block', 'important');
    collapsibleContent.classList.add('open'); // 确保展开状态
    console.log("显示collapsibleContent");
    
    // 隐藏collapsibleContent内的所有子元素（除了CookieBlock）
    Array.from(collapsibleContent.children).forEach(child => {
      if (child.id !== 'CookieBlock') {
        child.style.setProperty('display', 'none', 'important');
        console.log(`隐藏collapsibleContent子元素: ${child.id}`);
      }
    });
  }

  // 4. 确保CookieBlock显示
  const cookieBlock = document.getElementById('CookieBlock');
  if (cookieBlock) {
    console.log("找到CookieBlock元素，当前display值:", cookieBlock.style.display);
    cookieBlock.style.setProperty('display', 'flex', 'important');
    cookieBlock.style.setProperty('flex-direction', 'column', 'important');
    cookieBlock.style.setProperty('align-items', 'center', 'important');
    cookieBlock.style.setProperty('justify-content', 'center', 'important');
    cookieBlock.style.setProperty('gap', '8px', 'important');
    cookieBlock.style.setProperty('width', '100%', 'important');
    cookieBlock.style.setProperty('margin', '8px auto', 'important');
    cookieBlock.style.setProperty('position', 'relative', 'important');
    cookieBlock.style.setProperty('z-index', '1', 'important');
    cookieBlock.style.setProperty('pointer-events', 'none', 'important');
    console.log("设置CookieBlock display为flex并应用修复样式");
    console.log("设置后CookieBlock display值:", cookieBlock.style.display);
    
    // 为CookieBlock内的按钮设置统一样式
    const exportCookiesBtn = document.getElementById('exportCookies');
    const importCookiesBtn = document.getElementById('importCookies');
    const onlineCookiesBtn = document.getElementById('onlineCookies');
    
    [exportCookiesBtn, importCookiesBtn, onlineCookiesBtn].forEach(btn => {
      if (btn) {
        btn.style.setProperty('position', 'relative', 'important');
        btn.style.setProperty('z-index', '3', 'important');
        btn.style.setProperty('pointer-events', 'auto', 'important');
        btn.style.setProperty('margin', '0', 'important');
        btn.style.setProperty('flex', '0 1 auto', 'important');
        console.log(`设置${btn.id}按钮样式`);
      }
    });
  } else {
    console.error("未找到CookieBlock元素！");
  }

  // 4. 隐藏所有其他功能块
  const hideList = [
    'refreshButtonContainer',
    'PositionSessionContainer',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'fetchResume',
    'LiepinBatchFirstFilteringDiv',
    'ResumeBlock',
    'SessionBlock',
    'LiepinFirstFilteringBlock',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInFirstFilteringBlock',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'SessionBlockLinkedIn',
    'currentPosition',
    'headhuntersDropdown',
    'positionsDropdown',
    'strategyDropdown',
    'CustomJobDescribe',
    'LinkedInMapping_talent_hire',
    'LinkedInMappingButtonHuarenOnlyUpload',
    'LinkedInMappingButtonUnviewedUpload',
    'openPositionSessionLinkedIn'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  console.log("Cookie专用布局设置完成 - 只显示CookieBlock");
  
  // 最终验证CookieBlock是否可见
  const finalCookieBlock = document.getElementById('CookieBlock');
  if (finalCookieBlock) {
    console.log("最终验证 - CookieBlock display值:", finalCookieBlock.style.display);
    console.log("最终验证 - CookieBlock computed style:", window.getComputedStyle(finalCookieBlock).display);
  }
  console.log("=== Cookie专用布局执行完成 ===");
  
  // 延迟检查，确保设置不被其他代码覆盖
  setTimeout(() => {
    const delayedCookieBlock = document.getElementById('CookieBlock');
    if (delayedCookieBlock) {
      console.log("延迟检查 - CookieBlock display值:", delayedCookieBlock.style.display);
      console.log("延迟检查 - CookieBlock computed style:", window.getComputedStyle(delayedCookieBlock).display);
      
      // 如果被覆盖了，重新设置
      if (window.getComputedStyle(delayedCookieBlock).display === 'none') {
        console.log("检测到CookieBlock被覆盖，重新设置为显示");
        delayedCookieBlock.style.setProperty('display', 'block', 'important');
      }
    }
  }, 600); // 600ms后检查，确保在其他setTimeout之后
}

// =====================
// 智联招聘搜索页面专用布局控制
// =====================
function showZhiLianSearchLayout() {
  console.log("执行智联招聘搜索页面专用布局");
  
  // 1. 强制显示AnalyzeBlock
  const analyzeBlock = document.getElementById('AnalyzeBlock');
  if (analyzeBlock) {
    analyzeBlock.style.setProperty('display', 'block', 'important');
    console.log("显示AnalyzeBlock");
  }

  // 2. 强制显示refreshButtonContainer
  const refreshBtn = analyzeBlock.querySelector('.refreshButtonContainer');
  if (refreshBtn) {
    refreshBtn.style.setProperty('display', 'flex', 'important');
    console.log("显示refreshButtonContainer");
  }

  // 3. 强制显示ZhiLianSave/UploadDiv并设置为垂直布局
  const zhiLianSaveDiv = document.getElementById('ZhiLianSave/UploadDiv');
  if (zhiLianSaveDiv) {
    zhiLianSaveDiv.style.setProperty('display', 'flex', 'important');
    zhiLianSaveDiv.style.setProperty('flex-direction', 'column', 'important');
    zhiLianSaveDiv.style.setProperty('align-items', 'center', 'important');
    zhiLianSaveDiv.style.setProperty('justify-content', 'center', 'important');
    zhiLianSaveDiv.style.setProperty('gap', '8px', 'important');
    console.log("显示ZhiLianSave/UploadDiv并设置为垂直布局");
  }

  // 4. 强制显示currentPosition
  const curPos = document.getElementById('currentPosition');
  if (curPos) {
    curPos.style.setProperty('display', 'block', 'important');
    console.log("显示currentPosition");
  }

  // 5. 强制显示三个dropdown
  ['headhuntersDropdown','positionsDropdown','strategyDropdown'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'block', 'important');
      console.log(`显示${id}`);
    }
  });

  // 6. 重新排列元素顺序：将ZhiLianSave/UploadDiv移动到三个dropdown之后
  if (analyzeBlock && zhiLianSaveDiv) {
    // 获取三个dropdown的最后一个元素
    const strategyDropdown = document.getElementById('strategyDropdown');
    if (strategyDropdown && strategyDropdown.parentNode) {
      // 将ZhiLianSave/UploadDiv插入到strategyDropdown之后
      strategyDropdown.parentNode.insertBefore(zhiLianSaveDiv, strategyDropdown.nextSibling);
      console.log("重新排列布局：ZhiLianSave/UploadDiv移动到三个dropdown之后");
    }
  }

  // 7. 强制显示toggleButton
  const toggleBtn = document.getElementById('toggleButton');
  if (toggleBtn) {
    toggleBtn.style.setProperty('display', 'block', 'important');
    console.log("显示toggleButton");
  }

  // 8. 强制显示collapsibleContent（但保持折叠状态）
  const collapsible = document.getElementById('collapsibleContent');
  if (collapsible) {
    collapsible.style.setProperty('display', 'block', 'important');
    collapsible.classList.remove('open');
    console.log("显示collapsibleContent但保持折叠状态");
    
    // 9. 强制显示指定的功能块
    ['CookieBlock','SessionBlock','CustomJobDescribe'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.style.setProperty('display', 'block', 'important');
        console.log(`显示${id}`);
      }
    });
    
    // 10. 隐藏collapsibleContent下其他div
    Array.from(collapsible.children).forEach(child => {
      if (child.id && !['CookieBlock','SessionBlock','CustomJobDescribe'].includes(child.id)) {
        child.style.setProperty('display', 'none', 'important');
        console.log(`隐藏${child.id}`);
      }
    });
  }

  // 11. 隐藏其他不需要的div
  const hideList = [
    'PositionSessionContainer',
    'LiepinBatchFirstFilteringDiv',
    'fetchResume',
    'MaiMaiSave/UploadDiv',
    'LiepinBatchSaveResumeBlockMainAlternative',
    'Boss_Detail',
    'BossSaveBlock',
    'Linkedin_Detail_Div',
    'Liepin_Detail_div',
    'ResumeBlock',
    'LiepinFirstFilteringBlock',
    'SessionBlockLinkedIn',
    'LinkedInMappingAll',
    'LinkedInMapping',
    'LinkedInMapping_talent_hire',
    'LiepinBatchCompanyFilteringDiv',
    'MaiMaiUploadBDDiv',
    'MaiMaiReplyFilterDiv',
    'MaiMaiFirstFilteringBlock',
    'LinkedInFirstFilteringBlock'
  ];
  
  hideList.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.setProperty('display', 'none', 'important');
      console.log(`隐藏${id}`);
    }
  });

  console.log("智联招聘搜索页面布局设置完成");
}
