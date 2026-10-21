"""
----------------------------------------------------
 File Name:        sessionService
 Author:           hoges
 Created Date:     2025/10/16
 Last Modified:    2025/10/16
 Python Version:   
----------------------------------------------------
"""
import json
import os.path
from typing import List

from backend.core.api.anyJobApi import get_headhunters, get_positions, get_search_conditions, h5_ai_update_status, \
    get_ah_result_dict
from backend.core.config.anyJobConfig import ENUM_H5_AI_STATUS
from backend.core.entity.searchCondition import SearchCondition
from backend.core.entity.zhilian_search_condition import zhilian_search_conditon
from backend.core.logger.logger import get_logger
from backend.core.model.first_conversation_with_excel_data import first_conversation_with_excel_data
from backend.core.model.first_conversation_data import first_conversation_data
from backend.core.model.upload_screening_data import upload_screening_data
from backend.core.utils.path_util import path_util
from backend.manger import Manger
import pandas as pd

logger = get_logger(__name__)


class SearchConditionService:

    def __init__(self):
        pass

    def _build_search_variants(self, search_condition: SearchCondition) -> List[SearchCondition]:
        keyword_variants = search_condition.get_keyword_variants()
        if not keyword_variants:
            return [search_condition]

        search_variants: List[SearchCondition] = []
        for keyword in keyword_variants:
            variant = search_condition.clone()
            variant.keyword = keyword
            search_variants.append(variant)
        return search_variants

    def _resolve_search_variants(self, cookies_file_path: str, search_condition: SearchCondition) -> List[SearchCondition]:
        search_variants = self._build_search_variants(search_condition)
        if len(search_variants) <= 1:
            return search_variants

        preview_manager = Manger()
        preview_manager.set_cookies(cookies_file_path)

        primary_variant = search_variants[0]
        primary_total = preview_manager.get_candidate_total(
            zhilian_search_conditon.from_liepin_condition(primary_variant)
        )
        logger.info(f'搜索词预检：组合词【{primary_variant.keyword}】命中 {primary_total} 人')

        if primary_total > 0:
            logger.info('组合词已有结果，优先使用精确搜索')
            return [primary_variant]

        fallback_variants: List[SearchCondition] = []
        for variant in search_variants[1:]:
            total = preview_manager.get_candidate_total(
                zhilian_search_conditon.from_liepin_condition(variant)
            )
            logger.info(f'搜索词预检：回退词【{variant.keyword}】命中 {total} 人')
            if total > 0:
                fallback_variants.append(variant)

        if fallback_variants:
            logger.info(f'组合词无结果，启用 {len(fallback_variants)} 个回退关键词继续搜索')
            return fallback_variants

        logger.info('组合词与回退词均无结果，保留组合词继续执行一次正式搜索')
        return [primary_variant]

    def upload_screening(self, data: upload_screening_data):
        # 设置 ai 状态，变成初筛上传中
        h5_ai_update_status(data.position_id, ENUM_H5_AI_STATUS.RESUME_UPLOADING)

        manger = Manger()

        for cookies_file_name in data.inject_session.cookies_file_name_list:

            cookies_file_path = os.path.join(path_util.get_cookies_path(), cookies_file_name)

            logger.info(f'cookies地址为{cookies_file_path}')

            # 抽取策略
            search_condition_list = self.get_search_condition(data)

            for search_condition in search_condition_list:
                resolved_search_conditions = self._resolve_search_variants(cookies_file_path, search_condition)
                for resolved_search_condition in resolved_search_conditions:
                    zhilian_sc = zhilian_search_conditon.from_liepin_condition(resolved_search_condition)
                    manger.upload_screening(cookies_file_path, zhilian_sc, data.hunterId, data.position_id,
                                            data.positionName)

            logger.info(f"上传高潜成功,{cookies_file_name}结束完成")

    def first_conversation(self, data: first_conversation_data):

        h5_ai_update_status(data.position_id, ENUM_H5_AI_STATUS.CHATTING)

        manger = Manger()

        for cookies_file_name in data.inject_session.cookies_file_name_list:

            cookies_file_path = os.path.join(path_util.get_cookies_path(), cookies_file_name)

            logger.info(f'cookies地址为{cookies_file_path}')

            # 抽取策略
            search_condition_list = self.get_search_condition(data)
            manger.first_conversation_count = 0
            for search_condition in search_condition_list:
                if manger.first_conversation_count >= data.limit_count:
                    logger.info('会话数超出限制')
                    break
                resolved_search_conditions = self._resolve_search_variants(cookies_file_path, search_condition)
                for resolved_search_condition in resolved_search_conditions:
                    if manger.first_conversation_count >= data.limit_count:
                        logger.info('会话数超出限制')
                        break
                    if manger.pay_flag:
                        logger.info('账号发送次数超出')
                        break
                    zhilian_sc = zhilian_search_conditon.from_liepin_condition(resolved_search_condition)
                    manger.first_conversation(cookies_file_path, zhilian_sc, data.position_id, data.limit_count)
                    logger.info(f'发起会话数：{manger.first_conversation_count}')

            logger.info(f"初次会话发起完毕,{cookies_file_name}结束完成")

    def first_conversation_with_excel(self, data: first_conversation_with_excel_data):
        excel_path = path_util.get_excel_path()
        excel_name_path = os.path.join(excel_path, data.excel_name)
        df = pd.read_excel(excel_name_path)
        for cookies_file_name in data.cookies_file_name_list:
            manger = Manger()
            cookies_file_path = os.path.join(path_util.get_cookies_path(), cookies_file_name)
            logger.info(f'cookies地址为{cookies_file_path}')
            for index, row in df.iterrows():
                is_chat = row.get("is_chat")
                name = row.get("name")
                if not pd.isna(is_chat) and int(is_chat) in (1, 2, 3, 4):
                    logger.info(f'{name} 已处理, is_chat={is_chat}')
                    continue

                position_id = row['position_id']
                apply_position = row.get('apply_position')
                if pd.isna(apply_position):
                    apply_position = None

                lp_keywords = row.get('liepin_keywords')
                zl_sc = zhilian_search_conditon.from_excel_keywords(lp_keywords)
                if not zl_sc:
                    logger.info(f'{name} liepin_keywords 格式无效: {lp_keywords}')
                    continue

                parsed = zhilian_search_conditon.parse_liepin_keywords(lp_keywords)
                logger.info(f'{name} 高级搜索: 公司={parsed[0]}, 职位={parsed[1]}, 学校={parsed[2]}, 专业={parsed[3]}')

                h5_ai_update_status(position_id, ENUM_H5_AI_STATUS.CHATTING)
                result_flag = manger.first_conversation_with_excel(
                    cookies_file_path,
                    zl_sc,
                    position_id,
                    data.limit_count,
                    job_title_hint=apply_position,
                )
                if result_flag == 0:
                    df.loc[index, "is_chat"] = 1
                elif result_flag == 1:
                    df.loc[index, 'is_chat'] = 2
                    logger.info('会话数超出限制，停止后续行')
                    break
                elif result_flag == 2:
                    df.loc[index, 'is_chat'] = 4
                elif result_flag == 3:
                    df.loc[index, 'is_chat'] = 3
        df.to_excel(excel_name_path)

    def search_accounts(self, keyword):
        allHunterList = get_ah_result_dict(get_headhunters('all'))['results'] + \
                        get_ah_result_dict(get_headhunters('clients'))['results']

        if not keyword:
            return allHunterList

        filteredAccounts = []
        keywordLower = keyword.lower()

        for account in allHunterList:
            if keywordLower in account["Name"].lower():
                filteredAccounts.append(account)

        logger.info(f"搜索关键词: {keyword}, 找到 {len(filteredAccounts)} 个账号")
        return filteredAccounts

    def search_positions(self, hunterId, keyword):
        # 获取所有岗位数据
        all_positions = get_ah_result_dict(get_positions(hunterId))['results']

        if not keyword:
            # 如果没有关键词，返回所有岗位的原始数据
            return all_positions

        filtered_positions = []
        keyword_lower = keyword.lower()

        for position in all_positions:
            # 定义需要搜索的字段
            search_fields = [
                position.get("position_name", ""),
                position.get("company_name", ""),
                position.get("keywords_zh", ""),
                position.get("keywords_en", "")
            ]

            # 在所有字段中进行模糊搜索（支持中英文）
            for field in search_fields:
                if field and keyword_lower in field.lower():
                    filtered_positions.append(position)
                    break  # 找到匹配就跳出，避免重复添加

        logger.info(f"搜索关键词: {keyword}, 找到岗位 {len(filtered_positions)} 个")
        return filtered_positions

    def search_conditions(self, positionId, keyword):
        all_search_conditions = get_ah_result_dict(get_search_conditions(positionId))['results']

        if not keyword:
            return all_search_conditions

        filtered_search_conditions = []
        keyword_lower = keyword.lower()

        for search_condition in all_search_conditions:
            search_fields = {
                search_condition.get("name", '')
            }

            for field in search_fields:
                if field and keyword_lower in field.lower():
                    filtered_search_conditions.append(search_condition)
                    break

        logger.info(f'搜索策略 {keyword} , 找到策略 {len(filtered_search_conditions)} 个')
        return filtered_search_conditions

    def get_search_condition(self, data):
        if data.inject_session.strategyMode == 'cloud':
            logger.info('使用云端模式')

            if not data.inject_session.strategy_list:
                raise ValueError('云端模式需要提供策略数据')

            search_condition_list = []

            for strategy in data.inject_session.strategy_list:
                # 打印调试信息
                logger.info(f"接收到的策略对象keys: {strategy.keys()}")
                strategy_json_str = strategy.get('strategy')
                strategy_name = strategy.get('name', '未命名策略')

                if not strategy_json_str or (isinstance(strategy_json_str, str) and strategy_json_str.strip() == ''):
                    raise ValueError(f"策略 {strategy_name} 的 strategy 字段为空或缺失")

                try:
                    logger.info("开始解析JSON字符串...")
                    searchCondition = SearchCondition.from_json_str(strategy_json_str)
                    logger.info("JSON解析成功")
                    logger.info(f"正在注入云端策略: {strategy_name}")
                    search_condition_list.append(searchCondition)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {str(e)}")
                    logger.error(f"尝试解析的内容: {strategy_json_str[:500]}")
                    raise ValueError(f"策略JSON格式错误: {str(e)}")
                except Exception as e:
                    logger.error(f"处理策略时出错: {str(e)}")
                    import traceback
                    logger.error(f"完整错误堆栈: {traceback.format_exc()}")
                    raise

            return search_condition_list

        elif data.inject_session.strategyMode == 'upload':
            logger.info('使用上传模式')

            if not data.inject_session.strategy_name_list:
                raise ValueError("上传模式需要提供 sessionFileName")

            session_file_path_list = []
            search_condition_list = []
            for strategy_name in data.inject_session.strategy_name_list:
                session_file_path = os.path.join(path_util.get_session_path(), strategy_name)
                session_file_path_list.append(session_file_path)
                logger.info(f'策略文件: {session_file_path}')
                search_condition_list.append(SearchCondition.from_json_file(session_file_path))
                logger.info(f"上传策略解析成功")

            return search_condition_list

        elif data.inject_session.strategyMode == 'all':
            logger.info('使用所有策略')

            strategy_list = []

            for strategy in get_ah_result_dict(get_search_conditions(data.position_id))['results']:
                if strategy['strategy']:
                    strategy_list.append(SearchCondition.from_json_str(strategy['strategy']))

            return strategy_list


        else:
            raise ValueError(f"不支持的策略模式: {data.strategyMode}")
