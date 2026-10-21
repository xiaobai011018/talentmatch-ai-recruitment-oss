"""
@describe:
@fileName: mm_user.py
@time    : 2025/9/24 21:36
@author  : duke
"""
from .mm_job import MMJob


class User:
    def __init__(self, job_dict, **user_info):
        self.name = user_info['name']
        self.id = user_info['id']
        self.job_dict: dict[str, MMJob] = job_dict  # key pid

    def __setstate__(self, state):
        self.name = state['name']
        self.id = state['id']
        self.job_dict = state['job_dict']

    @property
    def __dict__(self):
        return {
            'name': self.name,
            'id': self.id,
            'job_dict': {k: v.__dict__ for k, v in self.job_dict.items()},
        }
