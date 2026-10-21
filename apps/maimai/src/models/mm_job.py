"""
@describe:
@fileName: mm_job.py
@time    : 2025/9/26 10:30
@author  : duke
"""


class MMJob:
    def __init__(self, **kwargs):
        self.position = kwargs['position']
        self.jid = kwargs['jid']
        self.ejid = kwargs['ejid']
