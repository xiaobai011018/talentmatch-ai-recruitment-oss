import copy
import json
import unittest

from backend.utils.highest_education import extract_highest_education


def education(school, major='', degree=''):
    return {'redSchool': school, 'redSpecial': major, 'redDegreeName': degree}


class HighestEducationTest(unittest.TestCase):
    def extract(self, records):
        return extract_highest_education(json.dumps({
            'base': {'eduExpFormList': records},
        }, ensure_ascii=False))

    def test_highest_degree_not_first_record_or_latest_date(self):
        records = [
            {**education('本科大学', '计算机', '本科'), 'redEnd': '2026'},
            {**education('硕士大学', '软件工程', '硕士'), 'redEnd': '2020'},
        ]
        self.assertEqual(self.extract(records), {'school': '硕士大学', 'major': '软件工程'})

    def test_degree_ranking_matches_extension(self):
        degrees = ('其它', '中专', '高中', '大专', '本科', '硕士', '博士', '博士后')
        for lower, higher in zip(degrees, degrees[1:]):
            for reverse in (False, True):
                with self.subTest(lower=lower, higher=higher, reverse=reverse):
                    records = [education('低学历学校', '', lower), education('高学历学校', '专业', higher)]
                    if reverse:
                        records.reverse()
                    self.assertEqual(self.extract(records), {'school': '高学历学校', 'major': '专业'})

    def test_english_degrees(self):
        for degree in ('Ph.D.', 'Doctorate', 'DPhil', '博士'):
            with self.subTest(degree=degree):
                self.assertEqual(self.extract([
                    education('Master University', 'Finance', 'Master'),
                    education('Doctor University', 'Economics', degree),
                ]), {'school': 'Doctor University', 'major': 'Economics'})

    def test_same_rank_preserves_source_order(self):
        self.assertEqual(self.extract([
            education('第一大学', '专业甲', '硕士'), education('第二大学', '专业乙', 'MBA'),
        ]), {'school': '第一大学', 'major': '专业甲'})

    def test_missing_major_is_not_borrowed_from_lower_degree(self):
        self.assertEqual(self.extract([
            education('本科大学', '计算机', '本科'), education('硕士大学', '', '硕士'),
        ]), {'school': '硕士大学', 'major': ''})

    def test_missing_school_is_not_borrowed_from_lower_degree(self):
        self.assertEqual(self.extract([
            education('本科大学', '计算机', '本科'), education('', '金融', '硕士'),
        ]), {'school': '', 'major': '金融'})

    def test_single_unranked_record_is_accepted(self):
        self.assertEqual(self.extract([education('唯一大学', '专业')]),
                         {'school': '唯一大学', 'major': '专业'})

    def test_multiple_unranked_records_are_not_guessed(self):
        self.assertEqual(self.extract([
            education('大学甲', '专业甲'), education('大学乙', '专业乙', '999'),
        ]), {'school': '', 'major': ''})

    def test_known_degree_takes_precedence_over_unknown_like_extension(self):
        self.assertEqual(self.extract([
            education('未知学历大学', '专业甲'), education('本科大学', '专业乙', '本科'),
        ]), {'school': '本科大学', 'major': '专业乙'})

    def test_placeholders_and_non_string_values_are_empty(self):
        for value in (None, '', '-', '--', '无', '暂无', '未知', '未填写',
                      'not found', 'NULL', 'undefined', [], {}, 123, True):
            with self.subTest(value=value):
                self.assertEqual(self.extract([education(value, value, '硕士')]),
                                 {'school': '', 'major': ''})

    def test_whitespace_and_markdown_are_normalized(self):
        self.assertEqual(self.extract([education(' **测试大学** ', ' Computer\n Science ', '本科')]),
                         {'school': '测试大学', 'major': 'Computer Science'})

    def test_empty_or_malformed_resume_is_safe(self):
        for raw in (None, '', '普通简历文本', '{broken', '[]', 'null', 42,
                    {}, {'base': None}, {'base': []}, {'base': {'eduExpFormList': {}}}):
            with self.subTest(raw=raw):
                self.assertEqual(extract_highest_education(raw), {'school': '', 'major': ''})

    def test_invalid_records_do_not_break_upload(self):
        self.assertEqual(self.extract([None, [], 'text', 1, {}, education('测试大学', '专业')]),
                         {'school': '测试大学', 'major': '专业'})

    def test_new_resume_view_education_list_is_supported(self):
        result = extract_highest_education({'base': {
            'eduExpFormList': [],
            'eduExperiences': [education('测试大学', '专业', '硕士')],
        }})
        self.assertEqual(result, {'school': '测试大学', 'major': '专业'})

    def test_does_not_read_work_experience_or_mutate_source(self):
        raw = {
            'base': {'eduExpFormList': [education('本科大学', '专业', '本科')]},
            'workExp': [education('博士公司', '技术总监', '博士')],
        }
        before = copy.deepcopy(raw)
        self.assertEqual(extract_highest_education(raw), {'school': '本科大学', 'major': '专业'})
        self.assertEqual(raw, before)


if __name__ == '__main__':
    unittest.main()
