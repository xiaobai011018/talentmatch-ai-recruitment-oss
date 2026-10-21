import json
import os.path
from backend.core.utils.path_util import path_util

def get_zhlian_code_by_liepin_dqname(dq_name,kind):
    with open(os.path.join(path_util.get_resource_path(),f'zhilian_{kind}_code.json'), "r", encoding="utf-8") as f:
        kind_list = json.load(f)
    for kind in kind_list['data']:
        if kind['label'] == dq_name:
            return kind['value']
        for region_children in kind['children']:
            if region_children['label'] == dq_name:
                return kind['value']