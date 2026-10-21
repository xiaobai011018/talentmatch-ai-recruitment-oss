import json
import copy

from backend.core.api.zhilian_api import get_candidate_list
from backend.core.entity.searchCondition import SearchCondition
from backend.core.utils.liepin_zhilian_map import get_zhlian_code_by_liepin_dqname


class zhilian_search_conditon:
    def __init__(self):
        self.filteringRead = False
        self.filteringChatted = True
        self.matchLatestWorkExperience = False
        self.filteringDownloaded = False
        self.filteringOtherChattedType = 'DONT_FILTER'
        self.sort = {
            "type": "COMPLEX",
            "version": 17
        }
        self.frontExperiment = True
        self.freeMaskLimit = False
        self.searchExperimentalGroup = 'EXPERIMENT'
        self.firstPageCacheable = False
        self.experiment = ''

    @classmethod
    def from_dict(cls, data: dict):
        obj = cls()

        for key in data.keys():
            value = data.get(key, None)
            # 仅当 value 不为空时才赋值
            if value not in (None, '', [], {}):
                setattr(obj, key, copy.deepcopy(value))
        return obj

    @classmethod
    def from_json_str(cls, str):
        return cls.from_dict(json.loads(str))

    @classmethod
    def from_json_file(cls, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_liepin_condition(cls, data: SearchCondition):
        obj = cls()
        if data.keyword:
            obj.keywordIntentions = {"keyword": data.keyword}
        if data.jobName or data.compName or data.school:
            obj.conditions = []
        if data.jobName:
            obj.conditions.append(
                {
                    'exactMatch': False,
                    'key': 'JOB',
                    'values': [f'{data.jobName}']
                })
        if data.compName:
            obj.conditions.append(
                {
                    'exactMatch': False,
                    'key': 'ORG',
                    'values': [f'{data.compName}']
                })
        if data.school:
            obj.conditions.append(
                {
                    'exactMatch': False,
                    'key': 'SCHOOL',
                    'values': [f'{data.school}']
                })
        if data.major:
            obj.majorNames = data.major
        if data.eduLevels:
            obj.educations = []
            education_map = {
                '060': '12',
                '050': '5',
                '040': '4',
                '030': '3',
                '010': '1'
            }
            for education_level in data.eduLevels:
                if education_level == '0100':
                    obj.educations.append('9')
                    obj.educations.append('7')
                else:
                    obj.educations.append(education_map[education_level])
        if data.ageHigh:
            obj.maxAge = int(data.ageHigh)
        if data.ageLow:
            obj.minAge = int(data.ageLow)
        if data.workYearsHigh:
            obj.maxWorkYears = int(data.workYearsHigh)
        if data.workYearsLow:
            obj.minWorkYears = int(data.workYearsLow)
        if data.schoolKindList:
            obj.schoolNatures = []
            school_kind_map = {
                '2': 'SCHOOL211',
                '1': 'SCHOOL985',
                '9': 'SCHOOL_DOUBLE_FIRST_CLASS'
            }
            for school_kind in data.schoolKindList:
                obj.schoolNatures.append(school_kind_map[school_kind])
        if data.eduLevelTzCode == '040':
            obj.schoolNatures = []
            obj.schoolNatures.append('UNIFIED')
        if data.studyAbroad:
            obj.schoolNatures = []
            obj.schoolNatures.append('SCHOOL_OVERSEASE')
        if data.activeStatus:
            active_time_map = {
                '01': 1,
                '02': 3,
                '03': 7,
                '04': 30,
                '05': 90,
                '06': 180,
                '07': 365
            }
            obj.activeTime = active_time_map[data.activeStatus]
        if data.sex:
            gender_map = {
                '1': '1',
                '2': '0'
            }
            obj.gender = gender_map[data.sex]
        if data.userHope:
            obj.careerStates = []
            hope_map = {
                '1': '2',
                '2': '1',
                '0': '4',
                '3': '3'
            }
            hope_list = data.userHope.split(',')
            for hope in hope_list:
                obj.careerStates.append(hope_map[hope])
        if data.wantDqsOut:
            obj.expectedCityIds = []
            for dqs in data.wantDqsOut:
                obj.expectedCityIds.append(get_zhlian_code_by_liepin_dqname(dqs.dqName, 'region'))
        if data.nowDqsOut:
            obj.currentCityIds = []
            for dqs in data.nowDqsOut:
                obj.currentCityIds.append(get_zhlian_code_by_liepin_dqname(dqs.dqName, 'region'))
        if data.industryArr or data.wantJobTitleArr:
            industry_map = {
                'H01': [100030000, 100040000, 100050000],
                'H0001': [100120000],
                'H02': [100010000, 100090000, 100140000],
                'H03': [400000000],
                'H04': [300000000],
                'H08': [500000000],
                'H0060': [500000000],
                'H09': [1200000000],
                'H14': [1100000000, 1100060000],
                'H0039': [700050000, 700060000],
                'H05': [700000000, 700010000, 700030000],
                'H0072': [700120000],
                'H06': [1300000000],
                'H0052': [500210000],
                'H0056': [1600020000],
                'H07': [1600000000],
                'H13': [1000000000],
                'H0106': [1000020000],
                'H0108': [700000000],
                'H0114': [1100050000],
                'H0120': [600000000],
                'H10': [800000000],
                'H11': [900000000],
                'H12': [1500000000],
                'H0118': [1400000000],
                'H0119': [1400000000]
            }
            if data.industryArr:
                obj.currentIndustries = []
                for industry in data.industryArr:
                    obj.currentIndustries = [*obj.currentIndustries, *industry_map[industry.code]]
            if data.wantJobTitleArr:
                obj.expectedIndustries = []
                for industry in data.wantIndustryArr:
                    obj.expectedIndustries = [*obj.expectedIndustries, *industry_map[industry.code]]
        if data.wantSalaryHigh:
            obj.expectedSalaryMax = int(int(data.wantSalaryHigh) * 10000 / 12) + 1
            if not data.wantSalaryLow:
                obj.expectedSalaryMin = 0
        if data.wantSalaryLow:
            obj.expectedSalaryMin = int(int(data.wantSalaryLow) * 10000 / 12) + 1
            if not data.wantSalaryLow:
                obj.expectedSalaryMin = 999999
        if data.resLanguage:
            if data.resLanguage == '0':
                obj.resumeLanguage = '1'
            else:
                obj.resumeLanguage = '2'
        if data.jobStability:
            if data.jobStability == '1':
                obj.jobHopping = [1]
            else:
                obj.jobHopping = [2]
        if data.filterViewed:
            obj.filteringRead = True
        if data.filterChat:
            obj.filteringChatted = True
        if data.filterDownload:
            obj.filteringDownloaded = True

        return obj

    @staticmethod
    def parse_liepin_keywords(lp_keywords: str):
        """解析 liepin_keywords：公司 职位 学校 专业（公司名可含空格）。"""
        if not lp_keywords or not str(lp_keywords).strip():
            return None
        parts = str(lp_keywords).split()
        if len(parts) < 4:
            return None
        major = parts[-1]
        school = parts[-2]
        job = parts[-3]
        company = ' '.join(parts[:-3])
        if not all([company, job, school, major]):
            return None
        return company, job, school, major

    @classmethod
    def from_excel_keywords(cls, lp_keywords: str):
        """Excel 高级搜索：对齐网页 Payload，城市不限，不过滤已聊候选人。"""
        parsed = cls.parse_liepin_keywords(lp_keywords)
        if not parsed:
            return None
        company, job, school, major = parsed
        obj = cls()
        obj.filteringChatted = False
        obj.conditions = [
            {'exactMatch': False, 'key': 'JOB', 'values': [job]},
            {'exactMatch': False, 'key': 'ORG', 'values': [company]},
            {'exactMatch': False, 'key': 'SCHOOL', 'values': [school]},
        ]
        obj.majorNames = major
        return obj

    def to_dict(self):
        result = {}
        for k, v in self.__dict__.items():
            if v not in (None, '', [], {}):
                result[k] = copy.deepcopy(v)
        return result

    def to_json_str(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_json_file(self, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=4)


# Manual demo removed from repository import; use synthetic fixtures for local testing.
