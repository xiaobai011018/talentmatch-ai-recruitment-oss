"""
@describe:
@fileName: search_condition.py
@time    : 2025/9/24 11:09
@author  : duke
"""
import json
from src.config.maimai import TEMPLATE_PAYLOAD_MM_SEARCH_BASIC
from copy import deepcopy


class SearchCondition:
    def __init__(self, condition_dict=None):
        # self.name = name

        self.cities = None
        self.degrees = None
        self.any_keyword = None
        self.want_dqs = None
        self.edu_levels = None
        self.age_high = None
        self.age_low = None
        self.want_salary_high_w = None
        self.want_salary_low_w = None
        self.work_years_high = None
        self.work_years_low = None
        self.job_name = None
        self.comp_name = None
        self.keywords = None
        if condition_dict:
            self.load_from_lp(condition_dict)

    def load_from_lp(self, condition_dict):

        self.keywords = condition_dict.get('keyword', '')
        self.keywords = self.keywords.replace('无效信息', '').strip()

        self.comp_name = condition_dict.get('compName', '')
        self.job_name = condition_dict.get('jobName', '')
        self.work_years_low = condition_dict.get('workYearsLow', '')
        self.work_years_high = condition_dict.get('workYearsHigh', '')
        self.want_salary_low_w = condition_dict.get('wantSalaryLow', '')
        self.want_salary_high_w = condition_dict.get('wantSalaryHigh', '')
        self.age_low = condition_dict.get('ageLow', '')
        self.age_high = condition_dict.get('ageHigh', '')
        self.edu_levels = condition_dict.get('eduLevels', [])
        self.want_dqs = condition_dict.get('wantDqsOut', [])
        self.any_keyword = condition_dict.get('anyKeyword', '0')

        if '050' in self.edu_levels:
            self.degrees = '0,1,2,3'
        elif '040' in self.edu_levels:
            self.degrees = '1,2,3'
        elif '030' in self.edu_levels:
            self.degrees = '2,3'
        elif '010' in self.edu_levels:
            self.degrees = '3'
        else:
            self.degrees = ''
        city_list = []
        for city in self.want_dqs:
            city_list.append(city['dqName'])
        self.cities = ','.join(city_list)

    def __str__(self):
        return f'{self.keywords}'

    def get_mm_payload(self, page=0, page_size=30) -> str:
        payload = deepcopy(TEMPLATE_PAYLOAD_MM_SEARCH_BASIC)

        payload_search = payload['search']

        payload_search['cities'] = self.cities
        payload_search['degrees'] = self.degrees
        payload_search['positions'] = ','.join(self.job_name.strip().split())
        payload_search['query'] = self.keywords
        payload_search['min_age'] = self.age_low
        payload_search['max_age'] = self.age_high
        payload_search['page'] = page
        payload_search['size'] = page_size
        payload_search['paginationParam']['size'] = page_size
        payload_search['paginationParam']['page'] = page
        payload_search['allcompanies'] = ','.join(self.comp_name.strip().split())
        payload_search['search_query'] = self.keywords
        payload_search['query_relation'] = self.any_keyword

        payload = json.dumps(payload)

        return payload
