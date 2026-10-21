if (typeof window.lastSelectedText === 'undefined') {
  window.lastSelectedText = "";
}
if (typeof window.SelectTextAlreadyHasResponse === 'undefined') {
  window.SelectTextAlreadyHasResponse = false;
}
if (typeof window.analyzedTextResults === 'undefined') {
  window.analyzedTextResults = {}; // 保存分析结果
}
if (typeof window.isMousedownInTextarea === 'undefined') {
  window.isMousedownInTextarea = false; // 用于记录 mousedown 事件是否发生在 textarea 内
}
if (typeof window.isElementActive === 'undefined') {
  window.isElementActive = false;
}

// Global helper function to reliably extract CSRF token from cookies
window.getCsrfTokenFromCookies = function () {
  console.log("Attempting to retrieve CSRF token from cookies globally");

  // Get all cookies
  const cookieStr = document.cookie;
  console.log("All cookies:", cookieStr);

  // First try regex approach for more reliable extraction
  const csrfTokenMatch = cookieStr.match(/csrftoken=([^;]+)/);
  if (csrfTokenMatch && csrfTokenMatch[1]) {
    console.log("Found csrftoken using regex:", csrfTokenMatch[1]);
    return csrfTokenMatch[1];
  }

  // Improved cookie parsing that handles values with = characters
  const cookies = {};
  cookieStr.split(';').forEach(cookie => {
    const parts = cookie.trim().split('=');
    if (parts.length >= 2) {
      const name = parts[0].trim();
      // Join back parts after the first = in case value contains = characters
      const value = parts.slice(1).join('=').trim();
      cookies[name] = value;
    }
  });

  console.log("Parsed cookies:", cookies);

  // Try different variations of the cookie name
  if (cookies['csrftoken']) {
    console.log("Found csrftoken in cookies:", cookies['csrftoken']);
    return cookies['csrftoken'];
  } else if (cookies[' csrftoken']) { // Note the space before name
    console.log("Found csrftoken with space prefix:", cookies[' csrftoken']);
    return cookies[' csrftoken'];
  } else if (cookies['csrf_token']) {
    console.log("Found csrf_token in cookies:", cookies['csrf_token']);
    return cookies['csrf_token'];
  } else if (cookies['X-CSRF-Token']) {
    console.log("Found X-CSRF-Token in cookies:", cookies['X-CSRF-Token']);
    return cookies['X-CSRF-Token'];
  }

  console.error("CSRF token not found in cookies globally");
  return null;
};

// 将文本替换为可点击的元素，并绑定点击事件
function makeTextClickable(text, result, posX, posY) {
  let span = document.createElement('span');
  span.className = 'clickableAnalyzedText';
  span.textContent = text;

  // 绑定点击事件，显示之前的结果
  span.addEventListener('click', function () {
    showResult(text, posX, posY);
  });

  // 使用 Range 对象替换选中内容
  let selection = window.getSelection();
  if (selection.rangeCount > 0) {
    let range = selection.getRangeAt(0);
    range.deleteContents();
    range.insertNode(span);
  }
}

// 移除页面上现有的输入框、按钮和结果div
function removeExistingElements() {
  let analyzeButtons = document.querySelectorAll('.AnalyzeInfomationButton');
  let analyzeInputs = document.querySelectorAll('.AnalyzeInput');
  let resultDivs = document.querySelectorAll('.resultDiv');

  analyzeButtons.forEach(button => {
    button.remove();
  });
  analyzeInputs.forEach(input => {
    input.remove();
  });
  resultDivs.forEach(div => {
    div.remove();
  });
  window.isElementActive = false; // 重置标志，允许再次创建新元素
}

// 显示分析结果
function showResult(text, posX, posY) {
  let resultDiv = document.createElement('div');
  resultDiv.className = 'resultDiv';
  resultDiv.style.position = 'absolute';
  resultDiv.style.top = `${posY - 1 / 9 * posY}px`;
  resultDiv.style.left = `${posX - 1 / 9 * posX}px`;
  resultDiv.style.backgroundColor = 'white';
  resultDiv.style.border = '2px solid #00FF00';  // 绿色边框
  resultDiv.style.padding = '10px';
  resultDiv.style.zIndex = 1000;
  resultDiv.style.maxWidth = '300px';
  resultDiv.style.maxHeight = '200px';
  resultDiv.style.overflowY = 'auto';

  // 让 div 更加显眼的其他样式
  resultDiv.style.boxShadow = '0 0 10px rgba(0, 255, 0, 0.5)'; // 绿色阴影
  resultDiv.style.borderRadius = '8px'; // 圆角边框
  resultDiv.style.fontWeight = 'bold'; // 加粗字体
  resultDiv.style.fontSize = '14px'; // 字体大小

  // 添加内容到结果div
  let resultContent = document.createElement('div');
  resultContent.textContent = window.analyzedTextResults[text];
  resultDiv.appendChild(resultContent);

  document.body.appendChild(resultDiv);
}

async function sendPromptToAPI(prompt, botID) {
  const formData = new FormData();
  const apiURL = "https://model.example.invalid/api/completions/quora.php";
  formData.append("chatbotID", botID);
  formData.append("userID", "__TALENTMATCH_USER_01__");
  formData.append("prompt", prompt);
  formData.append("permission", "1");

  try {
    const response = await fetch(apiURL, { method: "POST", body: formData });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const result = await response.json();
    return result.choices[0].message.content;
  } catch (error) {
    console.error("Error sending prompt to API:", error);
  }
}

// boss detail
chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  if (message.action === 'extractBossDetail') {
    try {
      const rawCompanyShort = document.querySelector(".company-info a[ka='job-detail-company_custompage']")?.textContent.trim() || '';
      const companyShort = rawCompanyShort.includes("..") ? '' : rawCompanyShort;

      const requestBody = {
        company: Array.from(document.querySelectorAll('.company-name')).pop()?.textContent.trim() || '',
        companyShort: companyShort,
        publishDate: document.querySelector('.gray')?.textContent.trim() || '',
        salary: document.querySelector('.salary')?.textContent.trim() || '',
        location: document.querySelector('.text-desc.text-city')?.textContent.trim() || '',
        platform: 'BOSS直聘',
        url: window.location.href,
        legalRepresentative: document.querySelector('.company-user')?.textContent.trim() || '',
        establishmentDate: document.querySelector('.res-time')?.textContent.trim() || '',
        registeredCapital: document.querySelector('.company-fund')?.textContent.trim() || '',
        address: document.querySelector('.location-address')?.textContent.trim() || '',
        recruitmentInfo: document.querySelector('.name h1')?.textContent.trim() || '',
        position: document.querySelector('.name span')?.textContent.trim() || '',
        jobRequirement: document.querySelector('.job-sec-text')?.textContent.trim() || '',
        companyType: document.querySelector('.company-type')?.textContent.trim() || '',
        encyclopedia: document.querySelector('.job-sec-text.fold-text')?.textContent.trim() || '',
        requirements: document.querySelector('.job-sec-text')?.textContent.trim() || '',
        workYears: document.querySelector('.text-desc.text-experiece')?.textContent.trim() || '',
        degree: document.querySelector('.text-desc.text-degree')?.textContent.trim() || '',
        jobStatus: document.querySelector('.job-status')?.textContent.trim() || '',
        iconStage: document.querySelector('.icon-stage')?.parentElement?.textContent.trim() || '',
        iconScale: document.querySelector('.icon-scale')?.parentElement?.textContent.trim() || '',
        iconIndustry: document.querySelector('.icon-industry')?.parentElement?.textContent.trim() || '',
        jobKeywords: Array.from(document.querySelectorAll('.job-keyword-list li')).map(li => li.textContent.trim()).join(', ') || '',
        hrPosition: document.querySelector('.boss-info-attr')?.textContent.trim() || '',
        HR_Name: Array.from(document.querySelectorAll('.name'))[2]?.textContent.trim() || '',
        yearLimit: document.querySelector('.text-desc.text-experiece')?.textContent.trim() || '',
        educationRequirement: document.querySelector('.text-desc.text-degree')?.textContent.trim() || '',
        principal: `${document.querySelector('.name h2')?.textContent.trim() || ''} ${document.querySelector('.boss-info-attr')?.textContent.trim() || ''}`.trim(),
        companyScale: Array.from(document.querySelectorAll('.sider-company p')).find(p => p.querySelector('.icon-scale'))?.textContent.trim() || '',
        financingStage: Array.from(document.querySelectorAll('.sider-company p')).find(p => p.querySelector('.icon-stage'))?.textContent.trim() || '',
        companyBusiness: document.querySelector('[ka="job-detail-brandindustry"]')?.textContent.trim() || '',
        jobAbroadDetail: extractJobAbroadDetail()
      };

      // 拼接 JobReq 属性
      const jobReqString = Object.entries(requestBody)
        .map(([key, value]) => `${key}: ${value}`)
        .join('\n');

      // 调用 API
      const apiResponse = await sendPromptToAPI(jobReqString, "__TALENTMATCH_MODEL_16__");
      requestBody.JobReq = apiResponse || '';

      console.log('extractBossDetail Request Body:', JSON.stringify(requestBody, null, 2));
      sendResponse(requestBody);
    } catch (error) {
      console.error('Error extracting boss detail:', error);
      sendResponse({ error: 'Failed to extract boss detail.' });
    }
  }
});



// 提取 job-abroad-detail 的函数
function extractJobAbroadDetail() {
  // 检查是否有 .job-abroad-detail 元素
  const abroadElements = document.querySelectorAll('.job-abroad-detail');
  if (abroadElements.length === 0) {
    console.warn('No elements found with class "job-abroad-detail".');
    return '';
  }

  // 提取所有 .job-abroad-detail 元素的文本内容，并清理多余的空白字符
  const details = Array.from(abroadElements)
    .map(elem => elem.textContent.trim().replace(/\s+/g, ' '))
    .join(' ');

  console.log('Extracted jobAbroadDetail:', details);
  return details;
}



// boss detail


// Mapping
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "startScraping") {
    console.log("Scraping started...");

    // 查找所有包含 'no-hover-tr' 类的行
    const rows = document.querySelectorAll('tr.no-hover-tr');
    const extractedData = [];

    rows.forEach((row, index) => {
      let name = "NoName";
      let gender = "Unknown";
      let age = null;
      let workYear = null;
      let degree = null;
      let location = null;
      let jobExpectation = null;
      let skills = [];
      let workExperience = [];
      let education = [];

      // Name
      try {
        name = row.querySelector('.c-name').textContent.trim();
      } catch (e) {
        console.log(`Row ${index + 1}: Name not found.`);
      }

      // Gender
      try {
        let genderImgSrc = row.querySelector('.c-name-wrap img').getAttribute('src');
        if (genderImgSrc.includes('female')) {
          gender = 'Female';
        } else if (genderImgSrc.includes('male')) {
          gender = 'Male';
        }
      } catch (e) {
        console.log(`Row ${index + 1}: Gender not found.`);
      }

      // Age, Work Year, Degree, Location
      try {
        let infoSpans = row.querySelectorAll('.c-info span');
        age = infoSpans[0].textContent.trim().replace("岁", "");
        workYear = infoSpans[1].textContent.trim();
        degree = infoSpans[2].textContent.trim();
        location = infoSpans[3].textContent.trim();
      } catch (e) {
        console.log(`Row ${index + 1}: Age, Work Year, Degree, or Location not found.`);
      }

      // Job Expectation
      try {
        jobExpectation = row.querySelector('.c-expect span').textContent.trim().replace('求职期望：', '').split('\xa0\xa0');
      } catch (e) {
        console.log(`Row ${index + 1}: Job Expectation not found.`);
      }

      // Skills
      try {
        let skillSpans = row.querySelectorAll('.c-skills-tag span');
        skillSpans.forEach(skillSpan => skills.push(skillSpan.textContent.trim()));
      } catch (e) {
        console.log(`Row ${index + 1}: Skills not found.`);
      }

      // Work Experience
      try {
        let workExpRows = row.querySelectorAll('.c-edu-wrap')[0].querySelectorAll('p');
        workExpRows.forEach(expRow => {
          let companyPosition = expRow.querySelector('.c-sp').textContent.trim().split(' · ');
          let company = companyPosition[0];
          let position = companyPosition[1];
          let time = expRow.querySelector('.c-time').textContent.trim().split('-');
          workExperience.push({
            company: company,
            position: position,
            timeStart: time[0],
            timeEnd: time[1].split('(')[0].trim(),
            timePeriod: time[1].split('(')[1].replace(')', '').trim()
          });
        });
      } catch (e) {
        console.log(`Row ${index + 1}: Work Experience not found.`);
      }

      // Education
      try {
        let eduRows = row.querySelectorAll('.c-edu-wrap')[1].querySelectorAll('p');
        eduRows.forEach(eduRow => {
          let universityData = eduRow.querySelector('.c-sp').textContent.trim().split(' · ');
          let university = universityData[0];
          let field = universityData[1];
          let degree = universityData[2];
          let admission = universityData[3];
          let time = eduRow.querySelector('.c-time').textContent.trim().split('-');
          education.push({
            university: university,
            field: field,
            degree: degree,
            admission: admission,
            timeStart: time[0],
            timeEnd: time[1].split('(')[0].trim(),
            timePeriod: time[1].split('(')[1].replace(')', '').trim()
          });
        });
      } catch (e) {
        console.log(`Row ${index + 1}: Education not found.`);
      }

      // 保存抓取的数据
      extractedData.push({
        name: name,
        gender: gender,
        age: age,
        workYear: workYear,
        degree: degree,
        location: location,
        jobExpectation: jobExpectation,
        skills: skills,
        workExperience: workExperience,
        education: education
      });
    });

    // 将抓取结果输出到控制台，或进行其他处理
    console.log(extractedData);

    // 发送抓取完成的消息并传回结果
    sendResponse({ message: "Scraping completed", data: extractedData });

    // 必须返回 true 表示这个消息处理是异步的
    return true;
  }
});
// Mapping

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getNumCount") {
    const el = document.querySelector('.t-14.flex.align-items-center.mlA.pl3 span');
    sendResponse({ numCount: el ? el.textContent.trim() : null });
  }
  return true; // Needed for async sendResponse
});

// 打开Session部分功能
chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
  if (request.jsonContent) {
    try {
      const jsonData = JSON.parse(request.jsonContent);

      // 检查是否是在 h.liepin.com 页面上
      if (window.location.host.includes('h.liepin.com')) {
        const payload = JSON.stringify(jsonData);
        sessionStorage.setItem('search_resume_session', payload);

        console.log('[Liepin注入] 已写入 search_resume_session');
        console.log('[Liepin注入] 策略字段:', Object.keys(jsonData));

        // 成功保存后刷新页面
        window.location.hash = '#session';
        location.reload();
        sendResponse({ status: 'success' });
      }
      // 检查是否是在 maimai.cn 页面上
      else if (window.location.host.includes('maimai.cn')) {
        console.log("Received maimai session data:", jsonData);

        // 初始化重试计数器和最大重试次数
        let retryCount = 0;
        const maxRetries = 3;

        // 定义注入函数，以便可以重试
        const injectMaimaiSession = () => {
          // 从jsonData中获取搜索条件
          const searchData = jsonData;
          const search = searchData.search;

          // 确认搜索框是否已加载
          const searchInput = document.querySelector('input[placeholder="按职位/公司/学校/专业等条件搜索人才"]');
          if (!searchInput) {
            console.log("搜索框还未加载，等待页面准备好...");
            // 如果尚未达到最大重试次数，则重试
            if (retryCount < maxRetries) {
              retryCount++;
              setTimeout(injectMaimaiSession, 1000); // 1秒后重试
              return;
            } else {
              console.error("无法找到搜索框，放弃注入");
              sendResponse({ status: 'error', message: '无法找到搜索框，放弃注入' });
              return;
            }
          }

          try {
            if (search && search.query) {
              searchInput.value = search.query;
              searchInput.dispatchEvent(new Event('input', { bubbles: true }));
              console.log("Filled search query:", search.query);
            }

          } catch (e) {
            console.error("Error processing maimai session data:", e);
            sendResponse({ status: 'error', message: '处理搜索数据失败: ' + e.message });
          }
        };

        // 首次尝试注入
        injectMaimaiSession();

        return true; // 异步响应
      }
      else {
        sendResponse({ status: 'error', message: 'Not on the correct page' });
      }
    } catch (e) {
      sendResponse({ status: 'error', message: 'Invalid JSON' });
    }
  }
});

// 保存Session部分功能（猎聘仅使用 search_resume_session）
function getSessionDataAndRemark() {
  const sessionData = sessionStorage.getItem('search_resume_session');

  const headhunterName = document
    .querySelector('a.quick-menu-item.name .name-val.ellipsis')
    ?.textContent.trim() || '';

  // 获取备注信息
  const industryElement = document.querySelector('.search-item.sfilter-industry');
  const otherSelectElement = document.querySelector(
    '.ant-select.h-select.sfilter-other-select.ant-select-lg.ant-select-single.ant-select-show-arrow'
  );
  const searchInputElement = document.querySelectorAll('.ant-select-selection-search-input')[1];
  const resumeNumElement = document.querySelector('.resume-num');

  const searchInputElement2 = document.querySelectorAll(
    '.ant-select.auto-select-base.ant-select-auto-complete.ant-select-lg.ant-select-single.ant-select-show-search input'
  )[1]?.value || '';

  const jobName = document.querySelectorAll('.ant-select-selection-search-input')[2]?.value || '';

  // 获取 class="es-margin-lr" 的元素内容并命名为 numberCount
  const numberCountElement = document.querySelector('.es-margin-lr');
  const numberCount = numberCountElement ? numberCountElement.textContent.trim() : '';

  // 拼接备注信息
  const remark = [
    industryElement ? " " + industryElement.textContent + "\n" : '',
    otherSelectElement ? "活跃度：" + otherSelectElement.textContent + "\n" : '',
    searchInputElement ? "搜索关键词：" + searchInputElement.value + "\n" : '',
    resumeNumElement ? resumeNumElement.textContent + "\n" : '',
    jobName ? "职位名称：" + jobName + '\n' : '',
    searchInputElement2 ? `公司名称： ${searchInputElement2}\n` : "没有填写公司名称"
  ].join(' ');

  return {
    sessionData,
    remark,
    numberCount,
    headhunterName
  };
}

// 监听来自 popup.js 的消息请求
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getSessionDataAndRemark') {
    const data = getSessionDataAndRemark();
    sendResponse(data);
  }

  return true;
});


function getSessionDataAndRemarkMaiMai() {
  // Initialize payload with default values
  const payload = {
    search: {
      cities: "",
      companyscope: 0,
      degrees: "",
      is_direct_chat: 0,
      positions: "",
      professions: "",
      provinces: "",
      query: "",
      schools: "",
      sortby: "0",
      worktimes: "",
      gender: "",
      age: "",
      salary: "",
      region_scope: "",
      ht_provinces: "",
      ht_cities: "",
      query_relation: 0,
      major: "",
      only_bachelor_degree: null,
      min_only_bachelor_degree: null,
      max_only_bachelor_degree: null,
      graduation_year: null,
      dynamic_valid_days: 90,
      has_social_relation: "",
      company_interaction: "",
      uploaded_resume: 0,
      delivered_or_can_chat: 0,
      job_hunting_status: [1, 4, 2],
      exclude_recently_viewed: 0,
      recently_untouched_valid_days: 0,
      remark: {
        remarked: 0,
        content: ""
      },
      in_project: 0,
      is_friend: 0,
      paginationParam: {
        page: 1,
        size: 1
      },
      page: 0,
      size: 1,
      sid: "",
      sessionid: "",
      highlight_exp: 1,
      data_version: "4.1",
      allcompanies: "",
      search_query: "",
      is_985: 0,
      is_211: 0,
      is_top_500: 0,
      is_world_500: 0,
      mapping_pfs: "",
      usePfUpdate: true,
      total: 1000,
      total_match: 1000
    }
  };

  // Scrape search query
  const searchInput = document.querySelector('input[placeholder="按职位/公司/学校/专业等条件搜索人才"]');
  if (searchInput) {
    payload.search.query = searchInput.value;
  }

  // Scrape active filters - look for elements with the class 'has-select-item___1mmdr'
  const activeFilters = document.querySelectorAll('.search-item-text.has-select-item___1mmdr');

  console.log(`Found ${activeFilters.length} active filters`);

  activeFilters.forEach(filter => {
    // Extract filter text, handling the case where the text might contain a colon
    const text = filter.textContent.trim();
    let key, value;

    // Check if the text contains a colon which indicates it's a filter with a value
    if (text.includes('：')) {
      const parts = text.split('：');
      key = parts[0].trim();
      value = parts.slice(1).join('：').trim(); // Join in case value itself contains colons

      console.log(`Extracted filter: ${key} = ${value}`);
      parseFilter(key, value, payload);
    } else {
      // This might be a filter title without a value yet
      console.log(`Found filter title without value: ${text}`);
    }
  });

  // Return payload as JSON string
  return { sessionData: JSON.stringify(payload) };
}

function parseFilter(key, value, payload) {
  // 清理输入值，移除可能的前缀
  let cleanValue = value;

  // 处理带前缀的值，例如 "期望/现居 - 深圳"
  if (value.includes(' - ')) {
    cleanValue = value.split(' - ')[1];
  } else if (value.includes('/') && value.includes('-')) {
    // 处理复杂格式
    const parts = value.split('-');
    cleanValue = parts[parts.length - 1].trim();
  }

  console.log(`Processing filter: ${key} with clean value: ${cleanValue}`);

  if (key === '城市地区') {
    payload.search.cities = cleanValue;
  } else if (key === '学历要求') {
    // 处理可能带有括号的学历信息
    const degreeMatch = cleanValue.match(/^(.*?)(?:\s*\(|$)/);
    payload.search.degrees = degreeMatch ? degreeMatch[1].trim() : cleanValue;

    if (cleanValue.includes('只看统招本科')) {
      payload.search.only_bachelor_degree = 1;
    }
  } else if (key === '工作年限') {
    payload.search.worktimes = cleanValue;
  } else if (key === '就职公司') {
    payload.search.allcompanies = cleanValue;
  } else if (key === '职位名称') {
    payload.search.positions = cleanValue;
  } else if (key === '毕业学校') {
    // 学校筛选可能有多种特殊情况
    payload.search.schools = cleanValue;

    if (cleanValue.includes('985')) payload.search.is_985 = 1;
    if (cleanValue.includes('211')) payload.search.is_211 = 1;
    if (cleanValue.includes('QS排名Top500')) payload.search.is_top_500 = 1;
    if (cleanValue.includes('海外Top500')) payload.search.is_world_500 = 1;
  } else if (key === '性别') {
    payload.search.gender = cleanValue;
  } else if (key === '年龄') {
    payload.search.age = cleanValue.replace('岁', '');
  } else if (key === '期望月薪') {
    payload.search.salary = cleanValue;
  } else if (key === '家乡') {
    payload.search.ht_cities = cleanValue;
  } else if (key === '专业') {
    payload.search.major = cleanValue;
  }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getSessionDataAndRemarkMaiMai') {
    const data = getSessionDataAndRemarkMaiMai();
    sendResponse(data);
  }
  return true; // Indicates asynchronous response
});


function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);

  const downloadLink = document.createElement("a");
  downloadLink.href = url;
  downloadLink.download = filename;
  document.body.appendChild(downloadLink);
  downloadLink.click();
  document.body.removeChild(downloadLink);
  URL.revokeObjectURL(url);
}


async function count_salary(salary) {
  const dict = await read_json_file('data/zhilian_rd_dict_cache.json')
  const cur_salary = Number(salary) * 10000 / 12;
  const salary_list = dict['NewSalary']['data'];
  if (!Number.isFinite(cur_salary) || cur_salary < 0) {
    return null;
  }
  if (cur_salary === 0) {
    return salary_list[0];
  }
  for (let i = 1; i < salary_list.length; i++) {
    const upperLimit = Number(salary_list[i][5]['upperLimit']);
    if (cur_salary <= upperLimit) {
      return salary_list[i];
    }
  }
  return salary_list[salary_list.length - 1];
}
//智联保存策略逻辑
async function save_zhilian_search_condition() {
  let session_data = {};

  const condition_el_list = document.getElementsByClassName('search-condition-result-new__item');
  const condition_list = [];
  for (let i = 0; i < condition_el_list.length; i++) {
    const condition_text = condition_el_list[i].textContent.trim();
    const kind = condition_text.split('：')[0];
    const value = condition_text.split('：')[1].trim();
    condition_list.push({ kind, value });
  }
  for (let i = 0; i < condition_list.length; i++) {
    const kind = condition_list[i].kind;
    const value = condition_list[i].value;
    if (kind === '关键词') {
      session_data.keywordIntentions = [{ "keyword": value }];
    }
    if (kind === '职位' || kind === '公司' || kind === '学校') {
      session_data.conditions = [];
      const key_map = {
        '职位': "JOB",
        '公司': "ORG",
        '学校': 'SCHOOL'
      };
      session_data.conditions.push(
        {
          "exactMatch": false,
          "key": key_map[kind],
          "values": value
        }
      );
    }
    if (kind === '专业') {
      session_data.majorNames = value;
    }
    if (kind === '学历要求') {
      const edu_lv_map = {
        '初中': '9',
        '高中': '7',
        '中专/中技': '12',
        '大专': '5',
        '本科': '4',
        '硕士': '3',
        'MBA/EMBA': '10',
        '博士': '1'
      };
      const edu_lv_list = ['9', '7', '12', '5', '4', '3', '10', '1'];
      if (value.includes('及')) {
        const edu_min_text = value.split('及')[0];
        session_data.educations = edu_lv_list.slice(edu_lv_list.indexOf(edu_lv_map[edu_min_text]));
      } else if (value.includes('-')) {
        const edu_min_text = value.split('-')[0];
        const edu_max_text = value.split('-')[1];
        session_data.educations = edu_lv_list.slice(edu_lv_list.indexOf(edu_lv_map[edu_min_text]), edu_lv_list.indexOf(edu_lv_map[edu_max_text]));
      }
    }
    if (kind === '年龄要求') {
      if (value.includes('及')) {
        session_data.minAge = parseInt(value.split('及')[0]);
        session_data.maxAge = 70;
      } else if (value.includes('-')) {
        const [minAge, maxAge] = value.split('-').map(v => parseInt(v));
        session_data.minAge = minAge;
        session_data.maxAge = maxAge;
      }
    }
    if (kind === '经验要求') {
      if (value === '无经验') {
        session_data.minWorkYears = 0;
        session_data.maxWorkYears = 0;
      } else if (value.includes('-')) {
        const [minWorkYears, maxWorkYears] = value.split('-').map(v => parseInt(v));
        session_data.minWorkYears = minWorkYears;
        session_data.maxWorkYears = maxWorkYears;
      }
    }
    if (kind === '院校要求') {
      session_data.schoolNatures = [];
      school_natures_map = {
        "统招": "UNIFIED",
        "985": "SCHOOL985",
        "211": "SCHOOL211",
        "双一流": "SCHOOL_DOUBLE_FIRST_CLASS",
        "海外院校": "SCHOOL_OVERSEASE"
      };
      if (value.includes('、')) {
        school_natures_list = value.split('、');
        for (let i = 0; i < school_natures_list.length; i++) {
          session_data.schoolNatures.push(school_natures_map[school_natures_list[i]]);
        }
      } else {
        session_data.schoolNatures.push(school_natures_map[value]);
      }
    }
    if (kind === '活跃日期') {
      if (value.includes("天")) {
        session_data.activeTime = parseInt(value[1]);
      }
      if (value.includes('周')) {
        session_data.activeTime = parseInt(value[1]) * 7;
      }
      if (value.includes('月')) {
        session_data.activeTime = parseInt(value[1]) * 30;
      }
      if (value.includes('年')) {
        session_data.activeTime = 365;
      }
    }
    if (kind === '性别') {
      if (value.includes('男')) {
        session_data.gender = '1';
      }
      if (value.includes('女')) {
        session_data.gender = '2';
      }
    }
    if (kind === '工作状态') {
      session_data.careerStates = [];
      if (value === '离职-找工作') {
        session_data.careerStates.push('2');
      }
      if (value === '在职-找工作') {
        session_data.careerStates.push('1');
      }
      if (value === '在职-看机会') {
        session_data.careerStates.push('4');
      }
      if (value === '在职-不找工作') {
        session_data.careerStates.push('3');
      }
    }
    // 期望月薪功能暂时注释，待实现 get_salary_number 函数后再启用
    /*
    if (kind === '期望月薪') {
      if (value.concat('及')) {
        session_data.expectedSalaryMin = get_salary_number(value.split('-')[0]);
        session_data.expectedSalaryMax = 999999;
      }
      if (value.concat('-')) {
        session_data.expectedSalaryMin = get_salary_number(value.split('-')[0]);
        session_data.expectedSalaryMax = get_salary_number(value.split('-')[1]);
      }
    }
    */
    if (kind === '人才类型') {
      session_data.resumeLevels = [];
      if (value === '校园人才') {
        session_data.resumeLevels.push('CAMPUS');
      }
      if (value === '金领人才') {
        session_data.resumeLevels.push('GOLD');
      }
    }
    if (kind === '人才照片') {
      if (value === '有照片') {
        session_data.includingAvatar = true;
      }
      if (value === '无照片') {
        session_data.includingAvatar = false;
      }
    }
    if (kind === '简历语言') {
      if (value === '中文简历') {
        session_data.resumeLanguage = '1';
      }
      if (value === '英文简历') {
        session_data.resumeLanguage = '2';
      }
    }
    if (kind === '跳槽频率') {
      session_data.jobHopping = [];
      if (value.includes('5')) {
        session_data.jobHopping.push(1);
      }
      if (value.includes('1')) {
        session_data.jobHopping.push(2);
      }
    }
    if (kind === '期望工作地') {
      session_data.expectedCityIds = [];
      if (value.includes('、')) {
        value_list = value.split('、')
        for (let i = 0; i < value_list.length; i++) {
          session_data.expectedCityIds.push(await get_code_by_name(value_list[i], "region"));
        }
      } else {
        session_data.expectedCityIds.push(await get_code_by_name(value, "region"));
      }
    }
    if (kind === '现居住地') {
      session_data.currentCityIds = [];
      if (value.includes('、')) {
        value_list = value.split('、')
        for (let i = 0; i < value_list.length; i++) {
          session_data.currentCityIds.push(await get_code_by_name(value_list[i], "region"));
        }
      } else {
        session_data.currentCityIds.push(await get_code_by_name(value, "region"));
      }
    }
    if (kind === '户口所在地') {
      session_data.huKouCityIds = [];
      if (value.includes('、')) {
        value_list = value.split('、')
        for (let i = 0; i < value_list.length; i++) {
          session_data.huKouCityIds.push(await get_code_by_name(value_list[i], "region"));
        }
      } else {
        session_data.huKouCityIds.push(await get_code_by_name(value, "region"));
      }
    }
    if (kind === '期望职位') {
      session_data.newExpectedJobTypes = [];
      if (value.includes('、')) {
        value_list = value.split('、')
        for (let i = 0; i < value_list.length; i++) {
          session_data.newExpectedJobTypes.push(await get_code_by_name(value_list[i], "position"));
        }
      } else {
        session_data.newExpectedJobTypes.push(await get_code_by_name(value, "position"));
      }
    }
    if (kind === '现从事职业') {
      session_data.newCurrentJobTypes = [];
      if (value.includes('、')) {
        value_list = value.split('、')
        for (let i = 0; i < value_list.length; i++) {
          session_data.newCurrentJobTypes.push(await get_code_by_name(value_list[i], "position"));
        }
      } else {
        session_data.newCurrentJobTypes.push(await get_code_by_name(value, "position"));
      }
    }
    if (kind === '期望行业') {
      session_data.expectedIndustries = [];
      if (value.includes('、')) {
        value_list = value.split('、')
        for (let i = 0; i < value_list.length; i++) {
          session_data.expectedIndustries.push(await get_code_by_name(value_list[i], "industry"));
        }
      } else {
        session_data.expectedIndustries.push(await get_code_by_name(value, "industry"));
      }
    }
    if (kind === '现从事行业') {
      session_data.currentIndustries = [];
      if (value.includes('、')) {
        value_list = value.split('、')
        for (let i = 0; i < value_list.length; i++) {
          session_data.currentIndustries.push(await get_code_by_name(value_list[i], "industry"));
        }
      } else {
        session_data.currentIndustries.push(await get_code_by_name(value, "industry"));
      }
    }
  }
  filter_list = document.getElementsByClassName('search-filter-new-action')[0].getElementsByClassName('km-checkbox__icon')
  if (filter_list[0].classList.length > 1) {
    session_data.filteringRead = true;
  } else {
    session_data.filteringRead = false;
  }
  if (filter_list[1].classList.length > 1) {
    session_data.filteringChatted = true;
  } else {
    session_data.filteringChatted = false;
  }
  if (filter_list[2].classList.length > 1) {
    session_data.matchLatestWorkExperience = true;
  } else {
    session_data.matchLatestWorkExperience = false;
  }
  session_data.filteringDownloaded = false;
  session_data.filteringOtherChattedType = 'DONT_FILTER';
  session_data.sort = {
    "type": "COMPLEX",
    "version": 17
  };
  session_data.frontExperiment = true;
  session_data.freeMaskLimit = false;
  session_data.searchExperimentalGroup = "EXPERIMENT";
  session_data.firstPageCacheable = false;
  session_data.experiment = "";
  sessionData = JSON.stringify(session_data);
  return { sessionData };
}

chrome.runtime.onMessage.addListener(async (request, sender, sendResponse) => {
  if (request.action === 'getSessionDataAndRemarkZhaopin') {
    try {
      const data = await save_zhilian_search_condition();
      const button = document.getElementById("save-filter-session");
      console.log("抓到的请求体(JSON字符串):", data);
      const session = data.sessionData
      const position_id = localStorage.getItem('selectedPosition');

      const params = new URLSearchParams({
        position_id: position_id,
        strategy: session
      })

      let is_duplicate = false

      await fetch('https://talent.example.invalid/api/duplicate_search_strategy.php', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: params.toString()
      })
        .then(response => response.json())
        .then(data => {
          if (data.duplicate === 'yes') {
            is_duplicate = true
            return Promise.reject('Duplicate found');
          }
          return data;
        });

      const formData = new FormData();
      formData.append("chatbotID", "__TALENTMATCH_MODEL_14__"); // 设置chatbotID
      formData.append("userID", "__TALENTMATCH_USER_01__"); // 设置userID
      formData.append("prompt", session); // 设置prompt为session数据
      formData.append("permission", "1"); // 设置权限为1

      if (!is_duplicate) {
        const response = await fetch('https://model.example.invalid/api/completions/quora.php', {
          method: 'POST',
          body: formData,
        });

        const data = await response.json();
        const content = data.choices[0]?.message?.content;
        console.log(`返回的内容: ${content}`);
        const positionID = localStorage.getItem("selectedPosition");
        const strategyFormData = new FormData();
        strategyFormData.append("position_id", positionID); // 向POST请求添加position_id字段
        strategyFormData.append("name", content); // 向POST请求添加name字段
        strategyFormData.append("strategy", session); // 向POST请求添加strategy字段
        strategyFormData.append("source", "zhilian");
        downloadFile(session, `${content}.json`, "application/json")
        downloadFile(session, `${content}.txt`, "text/plain")

        // 向add_search_strategy.php端点发送POST请求
        await fetch('https://talent.example.invalid/api/add_search_strategy.php', {
          method: 'POST',
          body: strategyFormData,
        });

        sendResponse({ success: true, message: "Strategy saved successfully", sessionData: session });
      } else {
        button.textContent = "Session重复";
        button.style.background = "grey";
        sendResponse({ success: false, message: "Duplicate session", sessionData: session });
      }
    } catch (err) {
      console.error("捕获请求体失败:", err);
      sendResponse({ error: err.message });
    }
  }
  return true; // 异步响应
});

async function read_json_file(filepath) {
  const url = chrome.runtime.getURL(filepath);
  const response = await fetch(url);
  const text = await response.text();
  const data = JSON.parse(text);
  return data
}

function findZhilianDictionaryItem(items, predicate) {
  for (const item of items || []) {
    if (predicate(item)) {
      return item;
    }
    if (Array.isArray(item.children)) {
      const match = findZhilianDictionaryItem(item.children, predicate);
      if (match) {
        return match;
      }
    }
  }
  return null;
}

async function get_code_by_name(name, kind) {
  const dict = await read_json_file(`data/zhilian_${kind}_code.json`);
  const item = findZhilianDictionaryItem(
    dict['data'],
    candidate => name === candidate.label
  );
  return item ? item.value : -1;
}

async function get_name_by_code(code, kind) {
  const dict = await read_json_file(`data/zhilian_${kind}_code.json`);
  const item = findZhilianDictionaryItem(
    dict['data'],
    candidate => code === candidate.value
  );
  return item ? item.label : -1;
}

function getLiepinMappedTargets(items, mappingData, kind) {
  const targets = [];
  const seenValues = new Set();
  for (const item of items || []) {
    const code = typeof item === "string" ? item : item && item.code;
    const name = typeof item === "string" ? item : item && item.name;
    let mapping = code && mappingData && mappingData.mappings
      ? mappingData.mappings[code]
      : null;
    if (!mapping && name && mappingData && mappingData.mappings) {
      const nameMatches = Object.values(mappingData.mappings).filter(
        candidate =>
          candidate.sourceName === name &&
          candidate.targets &&
          candidate.targets.length > 0
      );
      const targetSignatures = new Set(
        nameMatches.map(candidate =>
          candidate.targets
            .map(target => String(target.value))
            .sort()
            .join(',')
        )
      );
      if (targetSignatures.size === 1) {
        mapping = nameMatches[0];
      }
    }
    if (!mapping) {
      console.warn(`猎聘${kind}“${name || code}”没有可用的字典映射`);
      continue;
    }
    if (!mapping.targets || mapping.targets.length === 0) {
      console.warn(
        `猎聘${kind}“${name || mapping.sourceName || code}”未找到唯一的智联映射`
      );
      continue;
    }
    for (const target of mapping.targets) {
      if (seenValues.has(String(target.value))) {
        continue;
      }
      seenValues.add(String(target.value));
      targets.push({
        value: target.value,
        label: target.label
      });
    }
  }
  return targets;
}

async function mapLiepinJobTitlesToZhilian(
  items,
  getCode = get_code_by_name,
  mappingData = null
) {
  if (mappingData) {
    return getLiepinMappedTargets(items, mappingData, "职位");
  }

  const mappedJobTypes = [];
  for (const item of items || []) {
    const name = typeof item === "string" ? item : item && item.name;
    if (!name) {
      continue;
    }
    const code = await getCode(name, "position");
    if (code === -1) {
      console.warn(`未找到猎聘职位“${name}”对应的智联职位`);
      continue;
    }
    mappedJobTypes.push({
      value: code,
      label: name
    });
  }
  return mappedJobTypes;
}

async function mapLiepinCitiesToZhilian(items, getCode = get_code_by_name) {
  const mappedCities = [];
  for (const item of items || []) {
    const name = typeof item === "string" ? item : item && item.dqName;
    if (!name) {
      continue;
    }
    const code = await getCode(name, "region");
    if (code === -1) {
      console.warn(`未找到猎聘城市“${name}”对应的智联城市`);
      continue;
    }
    mappedCities.push({
      label: name,
      value: code
    });
  }
  return mappedCities;
}

function createDefaultZhilianCondition() {
  return {
    expectedCityIds: [],
    job: null,
    keyword: "",
    keywordTagList: [],
    jobKW: "",
    orgKW: "",
    schoolKW: "",
    majorKW: "",
    educations: null,
    schoolNatures: [],
    workYears: [],
    age: [],
    expectedSalary: [],
    activeTime: null,
    careerStates: [],
    expectedJobTypes: [],
    expectedIndustries: [],
    currentJobTypes: [],
    currentIndustries: [],
    currentCityIds: [],
    gender: null,
    resumeLanguage: null,
    includingAvatar: null,
    resumeLevels: null,
    languageSkills: [],
    huKouCityIds: [],
    filteringChatted: false,
    filteringRead: false,
    filteringDownloaded: false,
    sort: { "label": "综合排序", "key": "complex", "value": "COMPLEX", "version": 17 },
    filteringOtherChattedType: "DONT_FILTER",
    matchLatestWorkExperience: false,
    jobHopping: null
  };
}

async function inject_zhilian_strategy(selectedOption) {
  const sessionObj = JSON.parse(selectedOption);
  const condition = createDefaultZhilianCondition();
  if (sessionObj.frontExperiment) {
    console.info('导入为智联策略');
  } else {
    console.info('导入为猎聘策略')
    const [
      liepinIndustryMappingData,
      liepinPositionMappingData
    ] = await Promise.all([
      read_json_file('data/liepin_zhilian_industry_map.json'),
      read_json_file('data/liepin_zhilian_position_map.json')
    ]);
    condition.currentCityIds = await mapLiepinCitiesToZhilian(
      sessionObj.nowDqsOut
    );
    condition.expectedCityIds = await mapLiepinCitiesToZhilian(
      sessionObj.wantDqsOut
    );
    if (sessionObj.keyword) {
      condition.keywordTagList = [{
        "keyword": sessionObj.keyword
      }]
    }
    if (sessionObj.jobName) {
      condition.jobKW = sessionObj.jobName;
    }
    if (sessionObj.compName) {
      condition.orgKW = sessionObj.compName;
    }
    if (sessionObj.school) {
      condition.schoolKW = sessionObj.school;
    }
    if (sessionObj.major) {
      condition.majorKW = sessionObj.major;
    }
    if (sessionObj.eduLevels && sessionObj.eduLevels.length > 0) {
      const edu_lv_map = {
        '0100': 0,
        '060': 1,
        '050': 2,
        '040': 3,
        '030': 4,
        '010': 5
      };
      const zhilian_map = {
        '0100': {
          "realVal": [
            {
              "value": "7",
              "label": "高中"
            },
            {
              "value": "12",
              "label": "中专/中技"
            },
            {
              "value": "5",
              "label": "大专"
            },
            {
              "value": "4",
              "label": "本科"
            },
            {
              "value": "3",
              "label": "硕士"
            },
            {
              "value": "10",
              "label": "MBA/EMBA"
            },
            {
              "value": "1",
              "label": "博士"
            }
          ],
          "customValue": [
            {
              "value": "7",
              "label": "高中"
            }
          ],
          "value": "999"
        },
        '060': {
          "realVal": [
            {
              "value": "12",
              "label": "中专/中技"
            },
            {
              "value": "5",
              "label": "大专"
            },
            {
              "value": "4",
              "label": "本科"
            },
            {
              "value": "3",
              "label": "硕士"
            },
            {
              "value": "10",
              "label": "MBA/EMBA"
            },
            {
              "value": "1",
              "label": "博士"
            }
          ],
          "customValue": [
            {
              "value": "12",
              "label": "中专/中技"
            }
          ],
          "value": "999"
        },
        '050': {
          "realVal": [
            {
              "value": "5",
              "label": "大专"
            },
            {
              "value": "4",
              "label": "本科"
            },
            {
              "value": "3",
              "label": "硕士"
            },
            {
              "value": "10",
              "label": "MBA/EMBA"
            },
            {
              "value": "1",
              "label": "博士"
            }
          ],
          "customValue": [
            {
              "value": "5",
              "label": "大专"
            }
          ],
          "value": "999"
        },
        '040': {
          "realVal": [
            {
              "value": "4",
              "label": "本科"
            },
            {
              "value": "3",
              "label": "硕士"
            },
            {
              "value": "10",
              "label": "MBA/EMBA"
            },
            {
              "value": "1",
              "label": "博士"
            }
          ],
          "customValue": [
            {
              "value": "4",
              "label": "本科"
            }
          ],
          "value": "999"
        },
        '030': {
          "realVal": [
            {
              "value": "3",
              "label": "硕士"
            },
            {
              "value": "10",
              "label": "MBA/EMBA"
            },
            {
              "value": "1",
              "label": "博士"
            }
          ],
          "customValue": [
            {
              "value": "3",
              "label": "硕士"
            }
          ],
          "value": "999"
        },
        '010': {
          "realVal": [
            {
              "value": "1",
              "label": "博士"
            }
          ],
          "customValue": [
            {
              "value": "1",
              "label": "博士"
            }
          ],
          "value": "999"
        }
      };
      let min_lv = sessionObj.eduLevels[0];
      for (const lv of sessionObj.eduLevels) {
        if (edu_lv_map[min_lv] > edu_lv_map[lv]) {
          min_lv = lv;
        }
      }
      condition.educations = zhilian_map[min_lv];
    }
    if (sessionObj.eduLevelTz === true) {
      condition.schoolNatures.push({
        "label": "统招",
        "value": "UNIFIED"
      })
    }
    if (sessionObj.schoolKindList) {
      const map = {
        '2': {
          "label": "211",
          "value": "SCHOOL211"
        },
        '1': {
          "label": "985",
          "value": "SCHOOL985"
        },
        '9': {
          "label": "双一流",
          "value": "SCHOOL_DOUBLE_FIRST_CLASS"
        }
      };
      for (const schoolKind of sessionObj.schoolKindList) {
        if (map[schoolKind]) {
          condition.schoolNatures.push(map[schoolKind]);
        }
      }
    }
    if (sessionObj.studyAbroad) {
      condition.schoolNatures.push({
        "label": "海外院校",
        "value": "SCHOOL_OVERSEASE"
      });
    }
    if (sessionObj.workYearsLow || sessionObj.workYearsHigh) {
      let workYearsLow = null;
      let workYearsHigh = null;
      if (!sessionObj.workYearsLow) {
        workYearsLow = {
          "label": "无经验",
          "value": "0"
        };
      } else {
        workYearsLow = {
          "label": `${sessionObj.workYearsLow}年`,
          "value": sessionObj.workYearsLow
        };
      }
      if (sessionObj.workYearsHigh) {
        condition.workYears.push(workYearsLow);
        workYearsHigh = {
          "label": `${sessionObj.workYearsHigh}年`,
          "value": sessionObj.workYearsHigh
        };
        condition.workYears.push(workYearsHigh);
      } else {
        condition.workYears.push(workYearsLow);
      }
    }
    if (sessionObj.ageLow || sessionObj.ageHigh) {
      let ageLow = null;
      let ageHigh = null;
      if (!sessionObj.ageLow) {
        ageLow = {
          "label": "16岁",
          "value": "16"
        };
      } else {
        ageLow = {
          "label": `${sessionObj.ageLow}岁`,
          "value": sessionObj.ageLow
        };
      }
      if (sessionObj.ageHigh) {
        condition.age.push(ageLow);
        ageHigh = {
          "label": `${sessionObj.ageHigh}岁`,
          "value": sessionObj.ageHigh
        };
        condition.age.push(ageHigh);
      } else {
        condition.age.push(ageLow);
      }
    }
    if (sessionObj.wantSalaryLow || sessionObj.wantSalaryHigh) {
      let wantSalaryLow = null;
      let wantSalaryHigh = null;
      if (!sessionObj.wantSalaryLow) {
        wantSalaryLow = {
          "value": "0",
          "label": "1千以下",
          "values": {
            "lowerLimit": "0"
          }
        };
      } else {
        const cur_salary = await count_salary(sessionObj.wantSalaryLow);
        if (cur_salary) {
          wantSalaryLow = {
            "value": cur_salary[0],
            "label": cur_salary[2],
            "values": cur_salary[5]
          };
        }
      }
      if (sessionObj.wantSalaryHigh) {
        if (wantSalaryLow) {
          condition.expectedSalary.push(wantSalaryLow);
        }
        const cur_salary = await count_salary(sessionObj.wantSalaryHigh);
        if (cur_salary) {
          wantSalaryHigh = {
            "value": cur_salary[0],
            "label": cur_salary[2],
            "values": cur_salary[5]
          };
          condition.expectedSalary.push(wantSalaryHigh);
        }
      } else if (wantSalaryLow) {
        condition.expectedSalary.push(wantSalaryLow);
      }
    }
    if (sessionObj.activeStatus) {
      const map = {
        '01': {
          "label": "近1天",
          "value": 1
        },
        '02': {
          "label": "近3天",
          "value": 3
        },
        '03': {
          "label": "近1周",
          "value": 7
        },
        '04': {
          "label": "近1个月",
          "value": 30
        },
        '05': {
          "label": "近2个月",
          "value": 60
        },
        '06': {
          "label": "近6个月",
          "value": 180
        },
        '07': {
          "label": "近1年",
          "value": 365
        }
      };
      condition.activeTime = map[sessionObj.activeStatus];
    }
    condition.currentIndustries = getLiepinMappedTargets(
      sessionObj.industryArr,
      liepinIndustryMappingData,
      "行业"
    );
    condition.expectedIndustries = getLiepinMappedTargets(
      sessionObj.wantIndustryArr,
      liepinIndustryMappingData,
      "行业"
    );

    condition.currentJobTypes = await mapLiepinJobTitlesToZhilian(
      sessionObj.nowJobTitleArr,
      get_code_by_name,
      liepinPositionMappingData
    );
    condition.expectedJobTypes = await mapLiepinJobTitlesToZhilian(
      sessionObj.wantJobTitleArr,
      get_code_by_name,
      liepinPositionMappingData
    );
    if (sessionObj.sex) {
      const map = {
        '1': {
          "value": "1",
          "label": "男"
        },
        '0': {
          "value": "2",
          "label": "女"
        }
      };
      condition.gender = map[sessionObj.sex];
    }
    if (sessionObj.resLanguage) {
      const map = {
        '0': {
          "label": "中文简历",
          "value": "1"
        },
        '1': {
          "label": "英文简历",
          "value": "2"
        }
      };
      condition.resumeLanguage = map[sessionObj.resLanguage];
    }
    if (sessionObj.filterViewed) {
      condition.filteringRead = true
    }
    if (sessionObj.filterChat) {
      condition.filteringChatted = true
    }
    if (sessionObj.filterDownload) {
      condition.filteringDownloaded = true
    }
    if (sessionObj.jobStability) {
      if (sessionObj.jobStability === '1') {
        condition.jobHopping = {
          "label": "5年内工作经历<3",
          "value": 1
        }
      }
    }

  }

  let url = 'https://rd6.zhaopin.com/api/talent/search/saveQuickSearchCondition';

  let payload = {
    condition: JSON.stringify(condition),
    jobNumber: 'special-v2'
  };

  console.info(JSON.stringify(payload))

  let res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "include",
    body: JSON.stringify(payload)
  });

  let text = await res.text();
  console.log(res.status, text);
}

chrome.runtime.onMessage.addListener(async (msg, sender, sendResponse) => {
  if (msg.type === "inject_zhilian_strategy") {
    try {
      console.log("收到 inject_zhilian_strategy 消息", msg.selectedOption);
      await inject_zhilian_strategy(msg.selectedOption);
      sendResponse({ status: "ok" });
    } catch (err) {
      console.error("inject_zhilian_strategy 出错:", err);
      sendResponse({ status: "error", message: err.message });
    }
  }
  return true;
});


chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "insertCompanies") {
    insertCompanies(request.batch);
  }
});

// Function to insert companies into the search box
function insertCompanies(batch) {
  const inputBox = document.querySelector('.ant-select-selection-search-input'); // Adjust selector
  if (!inputBox) {
    alert("未找到公司筛选输入框!");
    return;
  }

  try {
    inputBox.value = batch.join(' '); // Insert companies with spaces
    inputBox.dispatchEvent(new Event('input', { bubbles: true })); // Simulate user input
    console.log("Inserted companies:", batch);
  } catch (error) {
    console.error("插入公司名称时发生错误:", error);
    alert("插入公司名称失败，请重试!");
  }
}

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  if (event.data && event.data.source === "maimai-extension" && event.data.type === "updateButton") {
    chrome.runtime.sendMessage({
      type: "updateButton",
      textContent: event.data.textContent,
      background: event.data.background,
      disabled: event.data.disabled,
    });
  }
});

// 划词分析部分
// 动态添加CSS样式（document_start 时 head 可能尚未存在）
function addGlobalStyle(css) {
  const inject = () => {
    const head = document.head || document.documentElement;
    if (!head) return;
    const style = document.createElement("style");
    style.type = "text/css";
    style.innerHTML = css;
    head.appendChild(style);
  };
  if (document.head) {
    inject();
  } else {
    document.addEventListener("DOMContentLoaded", inject, { once: true });
  }
}

// 添加动画的CSS
addGlobalStyle(`
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.9); }
  to { opacity: 1; transform: scale(1); }
}

@keyframes fadeOut {
  from { opacity: 1; transform: scale(1); }
  to { opacity: 0; transform: scale(0.9); }
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes resultFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.AnalyzeInfomationButton {
  animation: fadeIn 0.3s ease-in-out;
  z-index: 1001; /* 确保按钮在 textarea 之上 */
}

.AnalyzeInput {
  animation: slideIn 0.01s ease-in-out;
  z-index: 1000; /* 确保 textarea 在按钮之下 */
}

.resultDiv {
  animation: resultFadeIn 0.01s ease-in-out;
}

.fadeOut {
  animation: fadeOut 0.0s ease-in-out;
}

.clickableAnalyzedText {
  cursor: pointer;
  text-decoration: underline;
  font-weight: bold; /* 粗体 */
  color: inherit; /* 保持原有颜色 */
  animation: fadeIn 0.05s ease-in-out;
}

.spinner {
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-left-color: #4CAF50;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  animation: spin 1s linear infinite;
  position: absolute;
  z-index: 1001;
}
`);

// 监听 mousedown 事件
document.addEventListener('mousedown', function (event) {
  // 判断 mousedown 是否在 textarea 内
  if (event.target.classList.contains('AnalyzeInput')) {
    window.isMousedownInTextarea = true;
  } else {
    window.isMousedownInTextarea = false;
  }
});

document.addEventListener('mouseup', function (event) {
  if (window.isMousedownInTextarea) {
    return;
  }

  if (
    event.target.classList.contains('AnalyzeInfomationButton') ||
    event.target.classList.contains('AnalyzeInput') ||
    event.target.classList.contains('RemoveButton') ||
    event.target.closest('.resultDiv')
  ) {
    event.stopPropagation();
    return;
  } else {
    removeExistingElements();
  }

  let selectedText = window.getSelection().toString();
  if (selectedText.length > 0) {
    if (selectedText == window.lastSelectedText) {
      console.log(`最后一次选中的文字和当前选中的一致`);
      return;
    } else {
      if (!window.SelectTextAlreadyHasResponse) {
        removeExistingElements();
      } else {
        return;
      }
    }
    window.lastSelectedText = selectedText;

    window.isElementActive = true;

    // 创建并显示自定义 textarea
    let textarea = document.createElement('textarea');
    let defaultQuestion = "这是什么？";
    textarea.className = 'AnalyzeInput';
    // textarea.style.display = "none"
    textarea.style.backgroundColor = "rgba(255, 255, 255, 1)";
    textarea.placeholder = defaultQuestion;
    textarea.style.position = 'absolute';
    textarea.style.top = `${event.pageY}px`;
    textarea.style.left = `${event.pageX + 10}px`;
    textarea.style.zIndex = 1000;
    textarea.style.padding = '10px';
    textarea.style.border = '1px solid #ccc';
    textarea.style.borderRadius = '5px';
    textarea.style.fontSize = '14px';
    textarea.style.width = '1px';
    textarea.style.height = '1px';
    textarea.style.opacity = 0
    // textarea.style.display = "none"
    document.body.appendChild(textarea);

    // 创建并显示自定义按钮
    // 创建并显示自定义按钮
    let button = document.createElement('button');
    button.className = 'AnalyzeInfomationButton';
    button.style.position = 'absolute';

    // 设置按钮背景图像为 ahicon.png（来自扩展的资源）
    button.style.backgroundImage = 'url(' + chrome.runtime.getURL('ahicon.png') + ')';
    button.style.backgroundSize = 'contain'; // 确保图标尺寸适应按钮
    button.style.backgroundRepeat = 'no-repeat'; // 不重复背景图像
    button.style.backgroundPosition = 'center left'; // 图标居左，按钮内文本居右

    // 设置背景色为透明
    button.style.backgroundColor = 'transparent !important';

    // 设置按钮的宽度和高度
    button.style.width = '40px';
    button.style.height = '40px';


    // 获取 textarea 的位置信息
    const textareaRect = textarea.getBoundingClientRect();

    // 设置按钮的位置相对于 textarea 的位置
    button.style.top = `${textareaRect.bottom + window.scrollY + 10}px`; // 10px 在 textarea 的下方
    button.style.left = `${textareaRect.left + window.scrollX}px`; // 按钮与 textarea 左边对齐

    button.style.zIndex = 1001;
    button.style.color = 'white';
    button.style.border = 'none';
    button.style.padding = '5px 10px';
    button.style.borderRadius = '3px';
    button.style.cursor = 'pointer';
    button.style.fontSize = '12px';
    document.body.appendChild(button);

    // 调整按钮位置，防止被遮挡
    const resizeObserver = new ResizeObserver(() => {
      button.style.top = `${textarea.getBoundingClientRect().bottom + window.scrollY + 10}px`;
      button.style.left = `${textarea.getBoundingClientRect().left + window.scrollX}px`;
    });
    resizeObserver.observe(textarea);

    let removalTimer = setTimeout(() => {
      button.classList.add('fadeOut');
      textarea.classList.add('fadeOut');
      button.addEventListener('animationend', () => button.remove());
      textarea.addEventListener('animationend', () => textarea.remove());
      window.isElementActive = false;
      resizeObserver.disconnect();
    }, 5000);

    button.addEventListener('click', function (event) {
      clearTimeout(removalTimer);

      button.remove();
      textarea.remove();
      resizeObserver.disconnect();

      let spinner = document.createElement('div');
      spinner.className = 'spinner';
      spinner.style.top = `${textareaRect.bottom + window.scrollY + 10}px`;
      spinner.style.left = `${textareaRect.left + window.scrollX}px`;
      document.body.appendChild(spinner);

      event.preventDefault();
      event.stopPropagation();

      console.log('Button clicked');

      let inputValue = textarea.value;

      let formData = new FormData();
      formData.append('chatbotID', '__TALENTMATCH_MODEL_21__');
      formData.append('userID', '__TALENTMATCH_USER_01__');
      formData.append('prompt', `${inputValue} ${selectedText}`);
      formData.append('permission', '1');
      console.log('FormData constructed:', formData);

      fetch('https://model.example.invalid/api/completions/quora.php', {
        method: 'POST',
        body: formData
      })
        .then(response => {
          console.log('Response received:', response);
          return response.json();
        })
        .then(data => {
          console.log('Parsed response data:', data);
          window.analyzedTextResults[selectedText] = data.choices[0].message.content;
          makeTextClickable(selectedText, data.choices[0].message.content, event.pageX, event.pageY);
          spinner.remove();
          window.isElementActive = false;
        })
        .catch(error => {
          console.error('Error:', error);
          window.isElementActive = false;
          spinner.remove();
        });
    });

    textarea.addEventListener('click', function () {
      clearTimeout(removalTimer);
    });
  }
});

// 猎聘的关键词提取部分
// content.js
console.log("[content.js] 脚本已注入");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("[content.js] onMessage triggered, message =", message);

  if (message.action === 'extractLiepinDetail') {
    console.log("[content.js] 收到指令 'extractLiepinDetail'，开始提取数据...");

    // 提取对应的页面元素
    const jobTitle = document.querySelector('.job-title')?.innerText.trim() || '';
    const salary = document.querySelector('.salary')?.innerText.trim() || '';

    // .job-properties 下的若干 <span>，分别是 [0]: 地区, [2]: 年限, [4]: 学历
    const jobProperties = document.querySelector('.job-properties');
    let location = '';
    let experience = '';
    let education = '';
    if (jobProperties) {
      const spans = jobProperties.querySelectorAll('span');
      location = spans[0]?.innerText.trim() || '';
      experience = spans[2]?.innerText.trim() || '';
      education = spans[4]?.innerText.trim() || '';
    }

    // 联系人姓名、招聘者·公司名称
    const contactName = document.querySelector('.recruiter-container .name')?.innerText.trim() || '';
    const contactTitle = (() => {
      const el = document.querySelector('.recruiter-container .title-box');
      return el ? el.innerText.replace(/\s+/g, ' ').trim() : '';
    })();

    // 职位介绍及岗位需求
    const jobDesc = document.querySelector(
      '.job-intro-container .paragraph dd[data-selector="job-intro-content"]'
    )?.innerText.trim() || '';

    // 企业行业, 融资阶段, 人数规模, 职位地址
    let industry = '';
    let financingStage = '';
    let staffSize = '';
    let jobAddress = '';
    const companyOther = document.querySelector('.company-other');
    if (companyOther) {
      const labelBoxes = companyOther.querySelectorAll('.label-box');
      // labelBoxes[0]: 行业, 1: 融资阶段, 2: 人数规模, 3: 职位地址
      industry = labelBoxes[0]?.querySelector('.text')?.innerText.trim() || '';
      financingStage = labelBoxes[1]?.querySelector('.text')?.innerText.trim() || '';
      staffSize = labelBoxes[2]?.querySelector('.text')?.innerText.trim() || '';
      jobAddress = labelBoxes[3]?.querySelector('.text')?.innerText.trim() || '';
    }

    // 注册时间, 注册资本, 经营期限, 经营范围
    let regTime = '';
    let regCapital = '';
    let operatingPeriod = '';
    let operatingScope = '';
    const registerInfo = document.querySelector('.register-info');
    if (registerInfo) {
      const regBoxes = registerInfo.querySelectorAll('.label-box');
      // regBoxes[0]: 注册时间, 1: 注册资本, 2: 经营期限, 3: 经营范围
      regTime = regBoxes[0]?.querySelector('.text')?.innerText.trim() || '';
      regCapital = regBoxes[1]?.querySelector('.text')?.innerText.trim() || '';
      operatingPeriod = regBoxes[2]?.querySelector('.text')?.innerText.trim() || '';
      operatingScope = regBoxes[3]?.querySelector('.text')?.innerText.trim() || '';
    }

    // 公司简介
    const companyIntro = document.querySelector(
      '[data-selector="company-intro-container"] .paragraph-box .inner'
    )?.innerText.trim() || '';

    // 将信息封装到对象
    const requestBody = {
      title: jobTitle,
      salary: salary,
      location: location,
      experience: experience,
      education: education,
      contactName: contactName,
      contactTitle: contactTitle,
      jobDescription: jobDesc,
      industry: industry,
      financingStage: financingStage,
      staffSize: staffSize,
      jobAddress: jobAddress,
      regTime: regTime,
      regCapital: regCapital,
      operatingPeriod: operatingPeriod,
      operatingScope: operatingScope,
      companyIntro: companyIntro,
      // 方便在后续的接口中识别来源、或做记录
      platform: '猎聘',
      url: window.location.href
    };

    console.log("[content.js] 提取结果: ", JSON.stringify(requestBody, null, 2));

    // 返回数据给调用者（例如后台脚本/popup）
    sendResponse(requestBody);

    // 需要返回 true 以保持消息通道
    return true;
  }
});

// 猎聘公司名称
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  try {
    if (message.action === 'setCompanySearch') {
      const companyInput = document.querySelector('.rc_select_4_list');
      if (companyInput) {
        companyInput.value = message.companies; // Set the company names
        companyInput.dispatchEvent(new Event('input', { bubbles: true }));
        companyInput.dispatchEvent(new Event('change', { bubbles: true }));
        companyInput.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter' }));
        console.log(`Set company search to: ${message.companies}`);
        sendResponse({ success: true });
      } else {
        console.error('Company search input not found');
        sendResponse({ success: false, error: 'Company search input not found' });
      }
    } else if (message.action === 'clickAllCheck') {
      const allCheckCheckbox = document.querySelector('input[name="allCheck"]');
      if (allCheckCheckbox) {
        allCheckCheckbox.click();
        console.log("Clicked the 'allCheck' checkbox");
        sendResponse({ success: true });
      } else {
        console.error("No 'allCheck' checkbox found");
        sendResponse({ success: false, error: "No 'allCheck' checkbox found" });
      }
    } else if (message.action === 'clickBatchOpen') {
      const batchViewButton = document.querySelector('[data-tlg-elem-id="h_pc_search_batch_view_res_btn"]');
      if (batchViewButton) {
        batchViewButton.click();
        console.log("Clicked the batch view button");
        sendResponse({ success: true });
      } else {
        console.error("No batch view button found");
        sendResponse({ success: false, error: "No batch view button found" });
      }
    } else if (message.action === 'checkHasNextPage') {
      const pagination = document.querySelector("ul.ant-pagination.resume-list-pagebar");
      const currentPageElement = document.querySelector("li.ant-pagination-item-active");
      const currentPage = currentPageElement ? parseInt(currentPageElement.innerText) : 1;
      const nextPageElement = pagination?.querySelector(`li[title="${currentPage + 1}"]`);
      const hasNextPage = !!nextPageElement;
      console.log(`Checked for next page: ${hasNextPage}`);
      sendResponse({ hasNextPage });
    } else if (message.action === 'goToNextPage') {
      const pagination = document.querySelector("ul.ant-pagination.resume-list-pagebar");
      const currentPageElement = document.querySelector("li.ant-pagination-item-active");
      const currentPage = currentPageElement ? parseInt(currentPageElement.innerText) : 1;
      const nextPageElement = pagination?.querySelector(`li[title="${currentPage + 1}"]`);
      if (nextPageElement) {
        nextPageElement.click();
        console.log(`Navigated to page ${currentPage + 1}`);
        sendResponse({ success: true });
      } else {
        console.error("No next page to navigate");
        sendResponse({ success: false, error: "No next page to navigate" });
      }
    }
  } catch (error) {
    console.error(`Error in content script for action ${message.action}:`, error);
    sendResponse({ success: false, error: error.message });
  }
});

// 与AI交互部分的爬取信息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getLiepinKeywords") {
    console.log('接收到请求: getLiepinKeywords , Code:A1');

    function getLiepinKeywords() {
      let keywords = "";
      let keywordElement = document.querySelector('body');
      if (keywordElement) {
        keywords = keywordElement.innerText;
        // console.log('获取到的 body 内容:', keywords);

        // 使用正则表达式找到第一个 * 到第一个 ****** 之间的内容并替换为 **
        keywords = keywords.replace(/\*[^*]*\*{6}/, '**');
      } else {
        console.log('未找到 body 元素');
      }
      // console.log(`A1 Keyword:
      //   ${keywords}`)
      return keywords;
    }

    const keywords = getLiepinKeywords();
    sendResponse({ keywords: keywords });
    return true; // 保持消息通道开放
  }

  if (request.action === 'fetchResumeContent') {
    const hostname = window.location.hostname;
    const fullUrl = window.location.href;
    let resumeHtmlContent = '';

    console.log("@content.js - current hostname: ", hostname);
    console.log("@content.js - full URL: ", fullUrl);

    if (hostname.includes('liepin')) {
      if (fullUrl.includes('liepin.com/resume')) {
        // 捕获猎聘简历
        console.log("@TalentMatch - content.js: Mode - liepin");
        const resumeElement = document.querySelector('.G0UQv');
        resumeHtmlContent = resumeElement ? resumeElement.innerHTML : 'No content found';
        sendResponse({ html: resumeHtmlContent });
      } else if (fullUrl.includes('liepin.com/search')) {
        // 也就是猎聘的list
        console.log("@TalentMatch - content.js: Mode - Liepin - List");

        try {
          let liepinListResumeInfo = [];
          const resumeCards = document.querySelectorAll('.detail-resume-card-wrap');

          if (resumeCards.length === 0) {
            console.warn("No resume cards found on the page.");
          }

          console.log(`Found ${resumeCards.length} resume cards.`);

          for (let i = 0; i < resumeCards.length; i++) {
            const nameElement = resumeCards[i].querySelector('.new-resume-personal-name');
            if (nameElement) {
              // Generate a random 4-digit number
              const randomNum = Math.floor(1000 + Math.random() * 9000);
              // Append the random number to the existing textContent
              nameElement.textContent = `【${nameElement.textContent} ${randomNum}】`;
              console.log(`Modified text content for element ${i}: ${nameElement.textContent}`);
            } else {
              console.warn(`No name element found in resume card index ${i}.`);
            }

            // Push the modified HTML of the resume card to the array
            liepinListResumeInfo.push(resumeCards[i].innerHTML);
            console.log(`Processed element ${i} with content:\n${resumeCards[i].innerHTML}`);
          }

          let resumeHtmlContent = liepinListResumeInfo.join(''); // Concatenate into a single string if needed
          resumeHtmlContent = resumeHtmlContent.replace(/立即沟通/g, '【接下来是下一个候选人的信息】');
          resumeHtmlContent = "contentJS-SendToListBot" + resumeHtmlContent;

          console.log(`Prepared resume HTML content to send:\n${resumeHtmlContent}`);
          sendResponse({ html: resumeHtmlContent });

          return true; // This indicates that an asynchronous response will be sent
        } catch (error) {
          console.error("An error occurred while processing the resume cards:", error);
        }

      }

    } else if (hostname.includes('linkedin.com')) {

      if (fullUrl.includes('/sales/lead/')) {
        let resumeHtmlContent = '';

        // 捕获 class 为 mb4 的第一个元素其中的所有文字
        const mb4Element = document.querySelector('.mb4');
        if (mb4Element) {
          // 获取元素中的所有文字
          resumeHtmlContent = mb4Element.textContent;

          // 去除所有换行符和大于两个以上的空格
          resumeHtmlContent = resumeHtmlContent.replace(/\s+/g, ' ').trim();

          // 匹配 "See all interests" 和最近的 "Interests"
          const seeAllInterestsIndex = resumeHtmlContent.indexOf('See all interests');
          if (seeAllInterestsIndex !== -1) {
            const interestsIndex = resumeHtmlContent.lastIndexOf('Interests', seeAllInterestsIndex);
            if (interestsIndex !== -1) {
              // 删除从 "Interests" 到 "See all interests" 之间的所有内容，包括这两个字样本身
              resumeHtmlContent = resumeHtmlContent.slice(0, interestsIndex) + resumeHtmlContent.slice(seeAllInterestsIndex + 'See all interests'.length);
            }
          }
        }

        // 发送内容
        console.log(resumeHtmlContent);
        sendResponse({ html: resumeHtmlContent });
      }
      else if (fullUrl.includes('/in/')) {
        // 点击所有"see more"按钮并等待加载完成
        clickSeeMoreButtons().then(() => {
          // // 捕获LinkedIn - in履历
          console.log("@TalentMatch - content.js: Mode - LinkedIn - in");

          // 候选人的名字
          const candidateName = document.querySelector('.text-heading-xlarge');

          // 候选人的经验
          const experienceSection = document.querySelectorAll('section.artdeco-card[data-view-name="profile-card"]')[3];
          // 候选人的about
          const aboutSectionElement = document.querySelector('.display-flex.ph5.pv3');
          // 候选人自己写的简介
          const info = document.querySelector('.text-body-medium.break-words');

          if (candidateName) resumeHtmlContent += "Name: " + candidateName.textContent
          if (experienceSection) resumeHtmlContent += experienceSection.textContent;
          if (info) resumeHtmlContent += info.textContent;
          if (aboutSectionElement) resumeHtmlContent += aboutSectionElement.textContent

          // if (!experienceSection && !aboutSectionElement) resumeHtmlContent = 'No content found';
          resumeHtmlContent += experienceSection.textContent;
          resumeHtmlContent = resumeHtmlContent.replace(/\n/g, '');

          sendResponse({ html: resumeHtmlContent });
          console.log(resumeHtmlContent)
        }).catch(error => {
          console.error('Error clicking see more buttons:', error);
          resumeHtmlContent = 'No content found';
          sendResponse({ html: resumeHtmlContent });
        });

        return true; // Indicate that we will respond asynchronously
      } else if (fullUrl.includes('/sales/search')) {
        // 也就是领英的list
        console.log("@TalentMatch - content.js: Mode - LinkedIn - salesSearch");

        try {
          // 使用前缀选择器查找类名以 'p4 _vertical-scroll-results_' 开头的元素
          const scrollContainer = document.querySelector('[class^="overflow-x-hidden overflow-y-auto p4"]');

          if (scrollContainer) {
            // 定义滚动函数
            const scrollDown = () => {
              scrollContainer.scrollTop += 100; // 每次滚动100像素
              if (scrollContainer.scrollTop + scrollContainer.clientHeight >= scrollContainer.scrollHeight) {
                clearInterval(scrollInterval); // 如果滚动到容器底部，停止滚动
              }
            };

            // 设置每100毫秒滚动一次
            const scrollInterval = setInterval(scrollDown, 100);

            // 等待5秒以确保页面加载完成
            setTimeout(() => {
              clearInterval(scrollInterval); // 5秒后停止滚动

              // 调用 clickSeeMoreButtons 函数
              clickSeeMoreButtons();

              let temp = document.querySelector('[class^="artdeco-list background-color-white _border-search-results_"]');
              setTimeout(() => {
                if (temp) {
                  // 在内容开头添加标记
                  const marker = document.createTextNode('contentJS-SendToListBot ');
                  temp.prepend(marker);
                  console.log("From contentjs - temp", temp)

                  let resumeHtmlContent = temp.textContent
                    .replace(/\n/g, '') // 移除换行符
                    .replace(/Save this lead to your list and get alerts when they change jobs, post to LinkedIn, and more\./g, '')
                    .replace(/Save lead/g, '')
                    .replace(/Save/g, '')
                    .replace(/…see more/g, '')
                    .replace(/Send a personalized message—ask about their interests or mention your mutual connections\./g, '')
                    .replace(/mutual connection/g, '')
                    .replace(/\s\s+/g, ' ')
                    .replace(/Add [^ ]+ [^ ]+ to [^ ]+/g, '');

                  console.log(resumeHtmlContent);
                  sendResponse({ html: resumeHtmlContent });

                  // 移除先前添加的标记
                  marker.remove();
                } else {
                  console.error("Temp element not found.");
                  sendResponse({ error: "Temp element not found." });
                }
              }, 5000);
            }, 5000); // 5000毫秒 = 5秒
          } else {
            console.error("Scroll container not found.");
            sendResponse({ error: "Scroll container not found." });
          }
        } catch (error) {
          console.error("Error scrolling:", error);
          sendResponse({ error: error.message });
        }

      } else if (fullUrl.includes('/talent/search')) {
        // 捕获LinkedIn - talent search
        console.log("@TalentMatch - content.js: Mode - LinkedIn - /talent/search");

        let resumeHtmlContent = "";

        // 捕获页面中class="artdeco-entity-lockup__title ember-view"的第一个元素里的textContent并在前面加入"姓名："
        const nameSection = document.querySelector('.artdeco-entity-lockup__title.ember-view');
        if (nameSection) {
          resumeHtmlContent += "姓名：" + nameSection.textContent.trim() + "<br>";
          console.log("Name captured successfully");
        }

        // 捕获页面中class="artdeco-entity-lockup__subtitle ember-view"的第一个元素里的textContent并在前面加入"职位："
        const jobSection = document.querySelector('.artdeco-entity-lockup__subtitle.ember-view');
        if (jobSection) {
          resumeHtmlContent += "职位：" + jobSection.textContent.trim() + "<br>";
          console.log("Job captured successfully");
        }

        // 捕获页面中class="expandable-list expandable-stepper"的第二个元素里的textContent并在前面加入"教育："
        const eduSections = document.querySelectorAll('.expandable-list.expandable-stepper');
        if (eduSections.length > 1) {
          resumeHtmlContent += "教育：" + eduSections[1].textContent.trim() + "<br>";
          console.log("Education captured successfully");
        }

        // 捕获页面中class="lt-line-clamp__raw-line"的第一个元素里的textContent并在前面加入"总结："
        const summarySection = document.querySelector('.lt-line-clamp__raw-line');
        if (summarySection) {
          resumeHtmlContent += "总结：" + summarySection.textContent.trim() + "<br>";
          console.log("Summary captured successfully");
        }

        // 捕获页面中class="expandable-list expandable-stepper"的第一个元素里的textContent并在前面加入"经验："
        if (eduSections.length > 0) {
          resumeHtmlContent += "经验：" + eduSections[0].textContent.trim() + "<br>";
          console.log("Experience captured successfully");
        }

        // 捕获页面中class="personal-info"的第一个元素里的textContent并在前面加入"个人链接："
        const linkSection = document.querySelector('.personal-info');
        if (linkSection) {
          const linkText = linkSection.textContent.trim();

          // 正则表达式匹配第一个出现的 URL
          const urlRegex = /(https?:\/\/[^\s]+)/;
          const urlMatch = linkText.match(urlRegex);

          if (urlMatch && urlMatch[0]) {
            resumeHtmlContent += `个人链接：|${urlMatch[0]}|<br>`;
            console.log("Personal link captured and formatted successfully");
          } else {
            resumeHtmlContent += "个人链接：无有效链接<br>";
            console.log("No valid personal link found");
          }
        }

        const aboutSection = document.querySelector('[data-anonymize="person-blurb"]');
        if (aboutSection) {
          resumeHtmlContent += aboutSection.innerHTML;
          console.log("About section captured successfully");
        }

        if (!nameSection && !jobSection && !eduSections.length && !summarySection && !aboutSection && !linkSection) {
          resumeHtmlContent = 'No content found';
          console.log("No content found");
        }

        sendResponse({ html: resumeHtmlContent });
      }


    } else if (hostname.includes('maimai')) {
      if (fullUrl.includes('detail')) {
        // 脉脉部分
        console.log("@TalentMatch - content.js: Mode - Maimai - 1");
        let elements = document.createElement('div');
        // 工作经历
        let element1 = document.getElementsByClassName('list-group m-b-0')[0];
        // 教育经历
        let element2 = document.getElementsByClassName('list-group m-b-0')[1];
        // 名字
        let element_name = document.getElementsByClassName('contact_detail_name text-black-3')[0];

        let textBefore = document.createTextNode('姓名：');
        let textAfter = document.createTextNode('。');

        elements.appendChild(textBefore)
        if (element_name) {
          let clonedName = element_name.cloneNode(true);
          elements.appendChild(clonedName)
        }
        elements.appendChild(textAfter)
        if (element1) {
          let clonedElement1 = element1.cloneNode(true);
          elements.appendChild(clonedElement1);
        }
        if (element2) {
          let clonedElement2 = element2.cloneNode(true);
          elements.appendChild(clonedElement2);
        }

        // console.log(document.getElementsByClassName('list-group m-b-0')[1])
        let resumeHtmlContent = elements;
        console.log("@content.js resumeHtmlContent: \n", resumeHtmlContent.textContent);
        sendResponse({ html: resumeHtmlContent.textContent });


      } else if (fullUrl.includes('micro_resume')) {
        // 脉脉微简历部分
        console.log("@TalentMatch - content.js: Mode - Maimai - 2")
        const elements = document.querySelector('#root')
        resumeHtmlContent = elements

        console.log("@content.js resumeHtmlContent: \n", resumeHtmlContent.textContent)

        sendResponse({ html: resumeHtmlContent.textContent });
      }

    } else if (hostname.includes('anyhelper')) {
      const links = document.querySelectorAll('a');
      let clicked = 0;
      links.forEach(link => {
        if (link.textContent.includes('Read More')) {
          link.click();
          clicked++;
        }
      });
      console.log(`Clicked ${clicked} 'Read More' links`);

      // AnyJobs部分
      console.log("@TalentMatch - content.js: Mode - AnyJob")
      // 个人信息部分
      let element1 = document.getElementsByClassName('media-body col-12')[0]
      // 工作年限部分
      let element2 = document.getElementsByClassName('tab-pane gallery')[0]
      // 教育经历部分 
      let element3 = document.getElementsByClassName('tab-pane gallery')[1]
      // 项目经历部分
      let element4 = document.getElementsByClassName('tab-pane gallery')[2]

      resumeHtmlContent = element1
      resumeHtmlContent.appendChild(element2)
      resumeHtmlContent.appendChild(element3)
      resumeHtmlContent.appendChild(element4)

      // 换行代替
      // resumeHtmlContent = resumeHtmlContent.replace(/\n/g, '');
      console.log("resumeHtmlContent:", resumeHtmlContent.textContent)

      sendResponse({ html: resumeHtmlContent.textContent });
    } else {
      resumeHtmlContent = 'No content found';
      sendResponse({ html: resumeHtmlContent });
    }
    return true; // Indicate that we will respond asynchronously
  }

  // 亮高LinkedIn符合要求的候选人部分
  if (request.action === 'highlightNames') {
    const fullUrl = window.location.href;
    let namesArray = request.names;

    // 拆分 namesArray 成两个数组
    let str1Array = namesArray.map(name => name.split('|')[0]);
    let str2Array = namesArray.map(name => name.split('|')[1]);

    console.log('(1108)Received names to highlight:', str1Array, str2Array);

    // 查找所有 data-anonymize="person-name" 的 span 元素
    let spanElements = document.querySelectorAll('span[data-anonymize="person-name"]');
    if (fullUrl.includes('search/getConditionItem')) spanElements = document.querySelectorAll('.c-name');

    spanElements.forEach(span => {
      str1Array.forEach((name, index) => {
        if (span.textContent.trim().includes(name)) {
          console.log('(1108)Match found, highlighting span:', span);
          span.style.backgroundColor = 'yellow'; // 黄色高亮

          // 检查右边是否已添加过文字
          if (!span.textContent.includes(str2Array[index])) {
            // 创建一个包裹元素
            let wrapper = document.createElement('span');
            wrapper.style.position = 'relative';

            // 创建额外内容
            let additionalText = document.createElement('span');
            additionalText.textContent = ` ${str2Array[index]}`;
            additionalText.style.color = 'red'; // 根据需要设置样式
            additionalText.style.whiteSpace = 'nowrap'; // 禁止换行
            additionalText.style.overflow = 'visible'; // 确保内容可见
            additionalText.style.position = 'absolute'; // 使其定位相对于父元素
            additionalText.style.left = '100%'; // 让其显示在当前span右边
            additionalText.style.zIndex = '10'; // 确保其显示在其他元素之上

            // 悬停时显示完整内容
            additionalText.style.visibility = 'hidden'; // 默认隐藏
            wrapper.onmouseover = () => additionalText.style.visibility = 'visible';
            wrapper.onmouseout = () => additionalText.style.visibility = 'hidden';

            // 将文本包裹进wrapper
            span.parentNode.insertBefore(wrapper, span);
            wrapper.appendChild(span);
            wrapper.appendChild(additionalText);
          }

          // 额外操作: 如果网址包含特定字符串
          if (fullUrl.includes('https://h.liepin.com/search')) {
            // 查找父元素 class 为 "jsx-479584096 c-new-resume-card c-new-resume-card-search"
            let parent = span.closest('.jsx-479584096.c-new-resume-card.c-new-resume-card-search');
            if (parent) {
              console.log('Parent element found:', parent);
              // 在父元素中查找勾选框 class="ant-checkbox-input"
              let checkbox = parent.querySelector('.ant-checkbox-input');
              if (checkbox) {
                console.log('Checkbox found:', checkbox);
                console.log('Checkbox current state (checked):', checkbox.checked);
                if (!checkbox.checked) {
                  checkbox.click(); // 勾选复选框
                  console.log('Checkbox clicked:', checkbox);
                } else {
                  console.log('Checkbox was already checked:', checkbox);
                }
              } else {
                console.log('Checkbox not found within parent:', parent);
              }
            } else {
              console.log('Parent element with specified class not found for span:', span);
            }
          } else {
            console.log(`判断不在猎聘`)
          }
        }
      });
    });

    sendResponse({ status: 'completed' });
  }
});

// 辅助函数：点击所有"see more"按钮并等待加载完成
function clickSeeMoreButtons() {
  return new Promise((resolve, reject) => {
    try {
      const buttons = document.querySelectorAll('button');
      let clicked = 0;
      buttons.forEach(button => {
        if (button.textContent.includes('展开') || (button.textContent.includes('see more'))) {
          button.click();
          clicked++;
        }
      });
      console.log(`Clicked ${clicked} 'see more' buttons`);
      setTimeout(resolve, 200); // 等待2秒让内容加载完成
    } catch (error) {
      reject(error);
    }
  });
}

// 城市筛选处理
async function handleCityFilter(filterValue) {
  // 先检查是否有城市多选框，并确保"期望"和"现居"都被选中
  const checkboxes = document.querySelectorAll('.ant-checkbox-input');
  for (const checkbox of checkboxes) {
    if (!checkbox.checked) {
      checkbox.click();
      await new Promise(resolve => setTimeout(resolve, 200));
    }
  }

  // 查找城市搜索框
  const citySearchInput = document.querySelector('input[placeholder="请输入城市地区"]');
  if (citySearchInput) {
    citySearchInput.value = filterValue;
    citySearchInput.dispatchEvent(new Event('input', { bubbles: true }));
    console.log(`Set city search to: ${filterValue}`);

    // 等待搜索结果
    await new Promise(resolve => setTimeout(resolve, 500));

    // 尝试点击匹配的城市
    // 可能是热门城市或一级列表中的城市
    const options = document.querySelectorAll('.option___nxmry, .sub_span___tPr5f, .city-name');
    for (const option of options) {
      if (option.textContent.includes(filterValue)) {
        option.click();
        console.log(`Selected city: ${option.textContent}`);

        // 检查是否需要点击确认按钮
        const confirmBtn = document.querySelector('.mui-btn-primary');
        if (confirmBtn && confirmBtn.textContent.includes('确')) {
          confirmBtn.click();
          console.log(`Clicked confirm button for city`);
        }
        return;
      }
    }

    // 如果没有找到匹配的城市，尝试在历史选项中查找
    const historyTags = document.querySelectorAll('.historyTag___1I9fJ');
    for (const tag of historyTags) {
      if (tag.textContent.includes(filterValue)) {
        tag.click();
        console.log(`Selected history city: ${tag.textContent}`);
        return;
      }
    }
  }
}

// 学历筛选处理
async function handleEducationFilter(filterValue) {
  // 查找预设的学历选项
  const eduOptions = document.querySelectorAll('.list-item___1uP7v .content___6LPBl');
  for (const option of eduOptions) {
    if (option.textContent.includes(filterValue)) {
      option.click();
      console.log(`Selected education: ${option.textContent}`);
      return;
    }
  }

  // 如果没有预设选项匹配，尝试自定义
  const customizeItem = document.querySelector('.text___3CrAS');
  if (customizeItem && customizeItem.textContent.includes('自定义')) {
    customizeItem.click();
    console.log('Clicked education customize');

    // 等待自定义区域加载
    await new Promise(resolve => setTimeout(resolve, 500));

    // 点击确定按钮
    const confirmBtn = document.querySelector('.mui-btn-primary');
    if (confirmBtn) {
      confirmBtn.click();
      console.log('Confirmed custom education');
    }
  }
}

// 工作年限筛选处理
async function handleWorkExperienceFilter(filterValue) {
  // 查找预设的工作年限选项
  const workExpOptions = document.querySelectorAll('.list-item___1uP7v .content___6LPBl');
  for (const option of workExpOptions) {
    if (option.textContent.includes(filterValue)) {
      option.click();
      console.log(`Selected work experience: ${option.textContent}`);
      return;
    }
  }

  // 如果没有预设选项匹配，尝试自定义
  const customizeItem = document.querySelector('.text___3CrAS');
  if (customizeItem && customizeItem.textContent.includes('自定义')) {
    customizeItem.click();
    console.log('Clicked work experience customize');

    // 等待自定义区域加载
    await new Promise(resolve => setTimeout(resolve, 500));

    // 点击确定按钮
    const confirmBtn = document.querySelector('.mui-btn-primary');
    if (confirmBtn) {
      confirmBtn.click();
      console.log('Confirmed custom work experience');
    }
  }
}

// 公司筛选处理
async function handleCompanyFilter(filterValue) {
  // 先检查是否有公司多选框，并确保"正任职"和"曾任职"都被选中
  const checkboxes = document.querySelectorAll('.ant-checkbox-input');
  for (const checkbox of checkboxes) {
    if (!checkbox.checked) {
      checkbox.click();
      await new Promise(resolve => setTimeout(resolve, 200));
    }
  }

  // 查找是否有预设的公司选项
  const companyOptions = document.querySelectorAll('.list-item___1uP7v .content___6LPBl');
  for (const option of companyOptions) {
    if (option.textContent === filterValue) {
      option.click();
      console.log(`Selected company: ${option.textContent}`);
      return;
    }
  }

  // 如果没有预设选项匹配，尝试使用搜索框
  const companySearchInput = document.querySelector('input[placeholder="请输入就职公司"]');
  if (companySearchInput) {
    companySearchInput.value = filterValue;
    companySearchInput.dispatchEvent(new Event('input', { bubbles: true }));
    console.log(`Set company search to: ${filterValue}`);

    // 等待搜索结果
    await new Promise(resolve => setTimeout(resolve, 500));

    // 尝试从搜索结果中选择公司
    const searchResults = document.querySelectorAll('.list-item___1uP7v');
    for (const result of searchResults) {
      if (result.textContent.includes(filterValue)) {
        result.click();
        console.log(`Selected company from search: ${result.textContent}`);
        return;
      }
    }

    // 如果没有搜索结果，可能需要点击确认添加自定义公司
    const confirmBtn = document.querySelector('.mui-btn-primary');
    if (confirmBtn) {
      confirmBtn.click();
      console.log('Confirmed custom company');
    }
  }
}

// 职位名称筛选处理
async function handlePositionFilter(filterValue) {
  // 查找预设的职位选项
  const positionOptions = document.querySelectorAll('.list-item___1uP7v .content___6LPBl');
  for (const option of positionOptions) {
    if (option.textContent.includes(filterValue)) {
      option.click();
      console.log(`Selected position: ${option.textContent}`);
      return;
    }
  }

  // 如果没有预设选项匹配，尝试使用搜索框
  const positionSearchInput = document.querySelector('input[placeholder="请输入职位名称"]');
  if (positionSearchInput) {
    positionSearchInput.value = filterValue;
    positionSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
    console.log(`Set position search to: ${filterValue}`);

    // 等待搜索结果
    await new Promise(resolve => setTimeout(resolve, 500));

    // 尝试从搜索结果中选择职位
    const searchResults = document.querySelectorAll('.list-item___1uP7v');
    for (const result of searchResults) {
      if (result.textContent.includes(filterValue)) {
        result.click();
        console.log(`Selected position from search: ${result.textContent}`);
        return;
      }
    }

    // 如果没有搜索结果，可能需要点击确认添加自定义职位
    const confirmBtn = document.querySelector('.mui-btn-primary');
    if (confirmBtn) {
      confirmBtn.click();
      console.log('Confirmed custom position');
    }
  }
}

// 学校筛选处理
async function handleSchoolFilter(filterValue) {
  // 特殊处理985、211等预设选项
  if (filterValue === '985' || filterValue === '211' || filterValue.includes('Top500')) {
    const schoolOptions = document.querySelectorAll('.list-item___1uP7v .content___6LPBl');
    for (const option of schoolOptions) {
      if (option.textContent === filterValue) {
        option.click();
        console.log(`Selected school type: ${option.textContent}`);
        return;
      }
    }
  }

  // 一般学校名称搜索
  const schoolSearchInput = document.querySelector('input[placeholder="请输入毕业学校"]');
  if (schoolSearchInput) {
    schoolSearchInput.value = filterValue;
    schoolSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
    console.log(`Set school search to: ${filterValue}`);

    // 等待搜索结果
    await new Promise(resolve => setTimeout(resolve, 500));

    // 尝试从搜索结果中选择学校
    const searchResults = document.querySelectorAll('.list-item___1uP7v');
    for (const result of searchResults) {
      if (result.textContent.includes(filterValue)) {
        result.click();
        console.log(`Selected school from search: ${result.textContent}`);
        return;
      }
    }

    // 如果没有搜索结果，可能需要点击确认添加自定义学校
    const confirmBtn = document.querySelector('.mui-btn-primary');
    if (confirmBtn) {
      confirmBtn.click();
      console.log('Confirmed custom school');
    }
  }
}

// 性别筛选处理
async function handleGenderFilter(filterValue) {
  // 查找性别选项 (男/女/不限)
  const genderOptions = document.querySelectorAll('.list-item___1uP7v .content___6LPBl');
  for (const option of genderOptions) {
    if (option.textContent === filterValue) {
      option.click();
      console.log(`Selected gender: ${option.textContent}`);
      return;
    }
  }
}

// 年龄筛选处理
async function handleAgeFilter(filterValue) {
  // 年龄范围通常是自定义的
  // 查找确认按钮并点击
  const confirmBtn = document.querySelector('.mui-btn-primary');
  if (confirmBtn) {
    confirmBtn.click();
    console.log('Confirmed age filter');
  }
}

// 薪资筛选处理
async function handleSalaryFilter(filterValue) {
  // 薪资范围通常是自定义的
  // 查找确认按钮并点击
  const confirmBtn = document.querySelector('.mui-btn-primary');
  if (confirmBtn) {
    confirmBtn.click();
    console.log('Confirmed salary filter');
  }
}

// 家乡筛选处理
async function handleHometownFilter(filterValue) {
  // 查找家乡搜索框
  const hometownSearchInput = document.querySelector('input[placeholder="请输入家乡所在城市"]');
  if (hometownSearchInput) {
    hometownSearchInput.value = filterValue;
    hometownSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
    console.log(`Set hometown search to: ${filterValue}`);

    // 等待搜索结果
    await new Promise(resolve => setTimeout(resolve, 500));

    // 尝试点击匹配的城市
    const options = document.querySelectorAll('.option___nxmry, .sub_span___tPr5f');
    for (const option of options) {
      if (option.textContent.includes(filterValue)) {
        option.click();
        console.log(`Selected hometown: ${option.textContent}`);
        return;
      }
    }
  }
}

// 专业筛选处理
async function handleMajorFilter(filterValue) {
  // 查找专业搜索框
  const majorSearchInput = document.querySelector('input[placeholder="请输入专业"]');
  if (majorSearchInput) {
    majorSearchInput.value = filterValue;
    majorSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
    console.log(`Set major search to: ${filterValue}`);

    // 等待搜索结果
    await new Promise(resolve => setTimeout(resolve, 500));

    // 尝试从搜索结果中选择专业
    const searchResults = document.querySelectorAll('.list-item___1uP7v');
    for (const result of searchResults) {
      if (result.textContent.includes(filterValue)) {
        result.click();
        console.log(`Selected major from search: ${result.textContent}`);
        return;
      }
    }

    // 如果没有搜索结果，可能需要点击确认添加自定义专业
    const confirmBtn = document.querySelector('.mui-btn-primary');
    if (confirmBtn) {
      confirmBtn.click();
      console.log('Confirmed custom major');
    }
  }
}

// 通用筛选项处理
async function handleGenericFilter(filterValue) {
  // 通用的选项查找和点击
  const options = document.querySelectorAll('.list-item___1uP7v, .item');
  let found = false;

  for (const option of options) {
    if (option.textContent.includes(filterValue)) {
      option.click();
      console.log(`Selected option: ${option.textContent}`);
      found = true;
      break;
    }
  }

  if (!found) {
    // 如果是文本输入类型的筛选项
    const input = document.querySelector('.item-container input, .ant-input');
    if (input) {
      input.value = filterValue;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      console.log(`Set input filter to ${filterValue}`);

      // 寻找确认按钮并点击
      const confirmBtn = document.querySelector('.mui-btn-primary');
      if (confirmBtn) {
        confirmBtn.click();
        console.log(`Clicked confirm button`);
      }
    }
  }
}

(function talentMatchActivitySummaryAutoResume() {
  if (window.__talentMatchActivitySummaryResumeHooked) return;
  window.__talentMatchActivitySummaryResumeHooked = true;

  let lastInjectRequestAt = 0;

  function maybeResumeActivitySummary() {
    try {
      const raw = sessionStorage.getItem("talentMatchActivitySummaryState");
      if (!raw) return;
      const state = JSON.parse(raw);
      const href = location.href;
      const onProfile = /linkedin\.com\/in\//i.test(href);
      const onSalesSearch = /linkedin\.com\/sales\/search/i.test(href);

      const shouldInject =
        (state.phase === "profile" && onProfile) ||
        (state.phase === "returning" && onSalesSearch) ||
        (state.phase === "list" && onSalesSearch && state.pendingPageResume);

      if (!shouldInject) return;

      const now = Date.now();
      if (now - lastInjectRequestAt < 2500) return;
      lastInjectRequestAt = now;

      console.log("[ActivitySummary] auto-resume 触发 phase=", state.phase, href);
      chrome.runtime.sendMessage({ action: "talentMatchInjectActivitySummary" });
    } catch (e) {
      console.warn("[ActivitySummary] auto-resume check failed:", e);
    }
  }

  [300, 800, 1500, 3000, 5000, 8000, 12000].forEach((ms) => {
    setTimeout(maybeResumeActivitySummary, ms);
  });
  window.addEventListener("pageshow", () => setTimeout(maybeResumeActivitySummary, 400));
  // SPA 翻页不触发 pageshow：轮询 pendingPageResume 作为兜底
  setInterval(maybeResumeActivitySummary, 2000);
})();

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "processNextProfile") {  //background.js
    if (typeof processOneProfile !== "function") {
      console.warn("[ActivitySummary] processOneProfile is not available on this page");
      sendResponse({ ok: false, error: "processOneProfile is not available" });
      return false;
    }
    // do one “click → extract → sendResumeData” cycle,
    // then return, letting the next alarm tick pick up where you left off.
    processOneProfile().then(() => {
      sendResponse({ ok: true });
    });
    return true; // indicate async sendResponse
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getLoginDate") {
    const span = Array.from(document.querySelectorAll('div.BTVlw span'))
      .find(el => el.textContent.includes('最后一次登录时间'));

    if (span) {
      const match = span.textContent.match(/(\d{4}\/\d{2}\/\d{2})/);
      const date = match ? match[1].replace(/\//g, "-") + " 00:00:00" : "";
      sendResponse({ date });
    } else {
      sendResponse({ date: "" });
    }
  }
  return true; // 异步响应
});
