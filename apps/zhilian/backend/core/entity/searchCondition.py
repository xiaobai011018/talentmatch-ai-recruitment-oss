import copy
import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import backend.core.api.chatBotApi as chatBot
from backend.core.config.chatBotApiConfig import ENUM_MODEL_ID
from backend.core.logger.logger import get_logger
from backend.core.utils.dictMapper.eduLevelsDict import EduLevelDict
from backend.core.utils.dictMapper.RegionDict import RegionDict
from backend.core.utils.dictMapper.industryDict import IndustryDict

logger = get_logger(__name__)


@dataclass
class Region:
    dqName: str
    dqCode: str


@dataclass
class Industry:
    name: str
    code: str


@dataclass
class JobTitle:
    name: str
    code: str


@dataclass
class SearchCondition:
    keyword: str = ""
    jobName: str = ""
    compName: str = ""
    nowDqsOut: List[Region] = field(default_factory=list)
    wantDqsOut: List[Region] = field(default_factory=list)
    workYearsLow: str = ""
    workYearsHigh: str = ""
    graduate: bool = False
    schoolKindList: List[str] = field(default_factory=list)
    eduLevelTz: bool = False
    studyAbroad: bool = False
    eduLevels: List[str] = field(default_factory=list)
    eduLevelTzCode: str = ""
    industryArr: List[Industry] = field(default_factory=list)
    wantIndustryArr: List[Industry] = field(default_factory=list)
    nowJobTitleArr: List[JobTitle] = field(default_factory=list)
    wantJobTitleArr: List[JobTitle] = field(default_factory=list)
    userHope: str = ""
    modifytimeType: str = ""
    activeStatus: str = ""
    workAbroad: bool = False
    managerial: bool = False
    languageSkills: List[str] = field(default_factory=list)
    languageContent: str = ""
    wantSalaryLow: str = ""
    wantSalaryHigh: str = ""
    nowSalaryLow: str = ""
    nowSalaryHigh: str = ""
    nowCompKind: str = ""
    resLanguage: str = ""
    sex: str = ""
    ageLow: str = ""
    ageHigh: str = ""
    school: str = ""
    major: str = ""
    anyKeyword: str = ""
    jobPeriod: str = ""
    jobStability: str = ""
    compPeriod: str = ""
    filterViewed: bool = False
    filterChat: bool = False
    filterDownload: bool = False
    resumetype: str = ""
    sortType: str = ""
    curPage: int = 0
    searchType: str = ""

    @staticmethod
    def normalize_search_text(value: str) -> str:
        if not value:
            return ""

        normalized = value.replace("\r", " ").replace("\n", " ")
        normalized = re.sub(r"[，、；;｜|/\\+]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def get_keyword_variants(self) -> List[str]:
        normalized_keyword = self.normalize_search_text(self.keyword)
        if not normalized_keyword:
            return []

        variants: List[str] = [normalized_keyword]
        tokens = [token for token in normalized_keyword.split(" ") if token]

        # 任意关键词模式下，组合词搜不到时再回退到单词召回。
        if self.anyKeyword == '1' and len(tokens) > 1:
            variants.extend(tokens)

        deduped_variants: List[str] = []
        seen = set()
        for variant in variants:
            if variant not in seen:
                seen.add(variant)
                deduped_variants.append(variant)
        return deduped_variants

    def clone(self) -> "SearchCondition":
        return copy.deepcopy(self)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json_str(self):
        return json.dumps(asdict(self), ensure_ascii=False)

    def to_json_file(self, sessionFilePath: str):
        with open(sessionFilePath, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=4)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchCondition":
        def convert_region_list(lst):
            return [Region(**r) for r in lst]

        def convert_industry_list(lst):
            return [Industry(**i) for i in lst]

        def convert_jobtitle_list(lst):
            return [JobTitle(**j) for j in lst]

        data['keyword'] = cls.normalize_search_text(data.get("keyword", ""))
        data['jobName'] = cls.normalize_search_text(data.get("jobName", ""))
        data['compName'] = cls.normalize_search_text(data.get("compName", ""))
        data['major'] = cls.normalize_search_text(data.get("major", ""))


        return cls(
            keyword=data.get("keyword", ""),
            jobName=data.get("jobName", ""),
            compName=data.get("compName", ""),
            nowDqsOut=convert_region_list(data.get("nowDqsOut", [])),
            wantDqsOut=convert_region_list(data.get("wantDqsOut", [])),
            workYearsLow=data.get("workYearsLow", ""),
            workYearsHigh=data.get("workYearsHigh", ""),
            graduate=data.get("graduate", False),
            schoolKindList=data.get("schoolKindList", []),
            eduLevelTz=data.get("eduLevelTz", False),
            studyAbroad=data.get("studyAbroad", False),
            eduLevels=data.get("eduLevels", []),
            eduLevelTzCode=data.get("eduLevelTzCode", ""),
            industryArr=convert_industry_list(data.get("industryArr", [])),
            wantIndustryArr=convert_industry_list(data.get("wantIndustryArr", [])),
            nowJobTitleArr=convert_jobtitle_list(data.get("nowJobTitleArr", [])),
            wantJobTitleArr=convert_jobtitle_list(data.get("wantJobTitleArr", [])),
            userHope=data.get("userHope", ""),
            modifytimeType=data.get("modifytimeType", ""),
            activeStatus=data.get("activeStatus", ""),
            workAbroad=data.get("workAbroad", False),
            managerial=data.get("managerial", False),
            languageSkills=data.get("languageSkills", []),
            languageContent=data.get("languageContent", ""),
            wantSalaryLow=data.get("wantSalaryLow", ""),
            wantSalaryHigh=data.get("wantSalaryHigh", ""),
            nowSalaryLow=data.get("nowSalaryLow", ""),
            nowSalaryHigh=data.get("nowSalaryHigh", ""),
            nowCompKind=data.get("nowCompKind", ""),
            resLanguage=data.get("resLanguage", ""),
            sex=data.get("sex", ""),
            ageLow=data.get("ageLow", ""),
            ageHigh=data.get("ageHigh", ""),
            school=data.get("school", ""),
            major=data.get("major", ""),
            anyKeyword=data.get("anyKeyword", ""),
            jobPeriod=data.get("jobPeriod", ""),
            jobStability=data.get("jobStability", ""),
            compPeriod=data.get("compPeriod", ""),
            filterViewed=data.get("filterViewed", False),
            filterChat=data.get("filterChat", False),
            filterDownload=data.get("filterDownload", False),
            resumetype=data.get("resumetype", ""),
            sortType=data.get("sortType", ""),
            curPage=data.get("curPage", 0),
            searchType=data.get("searchType", ""),
        )

    @classmethod
    def from_json_str(cls, sessionJsonStr: str):
        return cls.from_dict(json.loads(sessionJsonStr))

    @classmethod
    def from_json_file(cls, sessionJsonFilePath: str):
        with open(sessionJsonFilePath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def set_fast_ai_session(self, fastStrategyText):
        for line in fastStrategyText.split("\n"):
            if "学历要求" in line:
                educationLevelRequirement = line.split("：")[1].strip()
                self.eduLevels = EduLevelDict().name_to_code(educationLevelRequirement)
            elif "年龄要求" in line:
                ageRequirement = line.split("：")[1].strip()
                self.ageLow = ageRequirement.split("-")[0].strip()
                self.ageHigh = ageRequirement.split("-")[1].stirp()
            elif "工作年限" in line:
                workExperience = line.split("：")[1].strip()
                self.workYearsLow = workExperience.split("-")[0].strip()
                self.workYearsHigh = workExperience.split("-")[1].strip()
            elif "薪资要求" in line:
                salaryRequirement = line.split("：")[1].strip()
                self.wantSalaryLow = salaryRequirement.split("-")[0].strip()
                self.wantSalaryHigh = salaryRequirement.split("-")[1].strip()
            elif "工作地点" in line:
                self.wantDqsOut = []
                workLocations = line.split("：")[1].strip().split(" ")
                for workLocation in workLocations:
                    self.wantDqsOut.append(Region(workLocation, RegionDict().nameToCode(workLocation)))

    def set_random_ai_session(self, randomStrategyText):
        for line in randomStrategyText.split("\n"):
            if "无有效信息" in line:
                continue
            if "简历描述关键词" in line:
                resumeDescriptionKeywords = line.split("：")[1].strip()
                self.keyword = resumeDescriptionKeywords
            elif "职位关键词" in line:
                jobTitleKeywords = line.split("：")[1].strip()
                self.jobName = jobTitleKeywords
            elif "公司名称关键词" in line:
                companyNameKeywords = line.split("：")[1].strip()
                self.compName = companyNameKeywords

    def set_ai_session(self, customerInfo):
        fastSessionText = chatBot.send(customerInfo,ENUM_MODEL_ID.GET_AI_FAST_STRATEGY)
        randomSessionText = chatBot.send(customerInfo, ENUM_MODEL_ID.GET_AI_RANDOM_STRATEGY)
        self.set_fast_ai_session(fastSessionText)
        self.set_random_ai_session(randomSessionText)

    def set_deep_ai_session(self, custerInfo):
        deepSessionText = chatBot.send(custerInfo, ENUM_MODEL_ID.GET_AI_DEEP_STRATEGY)
        for line in deepSessionText.split("\n"):
            if "无有效信息" in line:
                continue
            if "搜索词-产品" in line:
                searchProduct = line.split("：")[1].strip()
                self.keyword = f'{self.keyword} {searchProduct}'.strip()
            if "搜索词-核心技能" in line:
                searchCoreSkills = line.split("：")[1].strip()
                self.keyword = f'{self.keyword} {searchCoreSkills}'.strip()
            if "搜索词-次要技能" in line:
                searchSecondarySkills = line.split("：")[1].strip()
                self.keyword = f'{self.keyword} {searchSecondarySkills}'.strip()
            if "专业关键词" in line:
                searchMajor = line.split("：")[1].strip()
                self.major = f'{self.major} {searchMajor}'.strip()
            if "岗位-具体名称" in line:
                searchJobName = line.split("：")[1].strip()
                self.jobName = f'{self.jobName} {searchJobName}'.strip()
            if "岗位-核心词" in line:
                searchJobCoreWords = line.split("：")[1].strip()
                self.jobName = f'{self.jobName} {searchJobCoreWords}'
            if "岗位-大类名称" in line:
                searchJobCategoryName = line.split("：")[1].strip()
                self.jobName = f'{self.jobName} {searchJobCategoryName}'
            if "公司名-企业类型" in line:
                searchCompanyType = line.split("：")[1].strip()
                self.compName = f'{self.compName} {searchCompanyType}'
            if "公司名-细分行业精准词" in line:
                searchCompanyIndustryWords = line.split("：")[1].strip()
                self.compName = f'{self.compName} {searchCompanyIndustryWords}'
            if "当前行业" in line:
                industryChNames = line.split("：")[1].strip().split(" ")
                industryList: List[Industry] = []
                for industryChName in industryChNames:
                    code = IndustryDict().chName_to_code(industryChName)
                    if code:
                        industryList.append(Industry(code=code, name=industryChName))
                    else:
                        # 如果没找到，仍然构造 Industry，code 填 None 或 ""
                        industryList.append(Industry(code="", name=industryChName))

                self.industryArr = industryList
            if "公司名-竞争对手" in line:
                searchCompanyCompetitors = line.split("：")[1].strip()
                self.compName = f'{self.compName} {searchCompanyCompetitors}'
            if "搜索词-客户名" in line:
                searchCustomerName = line.split("：")[1].strip()
                self.keyword = f'{self.keyword} {searchCustomerName}'.strip()
            if "搜索词-市场名" in line:
                searchMarketName = line.split("：")[1].strip()
                self.keyword = f'{self.keyword} {searchMarketName}'.strip()
            if "工作城市" in line:
                workLocations = line.split("：")[1].strip().split(" ")
                for workLocation in workLocations:
                    self.wantDqsOut.append(Region(workLocation, RegionDict().nameToCode(workLocation)))
            if "附近城市" in line:
                nearWorkLocations = line.split("：")[1].strip().split(" ")
                for nearWorkLocation in nearWorkLocations:
                    self.wantDqsOut.append(Region(nearWorkLocation, RegionDict().nameToCode(nearWorkLocation)))





# Manual demo removed from repository import; use synthetic fixtures for local testing.
