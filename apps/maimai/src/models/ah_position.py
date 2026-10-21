"""
@describe:
@fileName: ah_position.py
@time    : 2025/9/26 15:30
@author  : duke
"""


class AHPosition:
    def __init__(self, pid, incharge_id, **kwargs):
        self.name = kwargs['position_name']
        self.pid = pid
        self.incharge_id = incharge_id
        self.requirement = kwargs.get('summary', None)
        self.jd = kwargs.get('description', None)
        self.second_requirement = "深匹要求："+ kwargs.get('summary',"").split("深匹要求：")[1] + kwargs.get('name_summary',"").split('【公司信息】')[0]
