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
import shutil
from datetime import datetime
from uuid import uuid4
import pandas as pd
from backend.api.anyJobApi import get_headhunters, get_positions, get_search_conditions, h5_ai_update_status, \
    get_ah_result_dict
from backend.config.anyJobConfig import ENUM_H5_AI_STATUS
from backend.entity.searchCondition import SearchCondition
from backend.logger.logger import get_logger
from backend.model.first_conversation_data import first_conversation_data
from backend.model.upload_screening_data import upload_screening_data
from backend.utils.filePathUtils.FilePathUtils import get_save_path, resolve_cookie_path, resolve_excel_path, \
    get_excel_result_dir
from backend.manger import Manger

logger = get_logger(__name__)


class SearchConditionService:

    def __init__(self):
        pass

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
                session_file_path = os.path.join(get_save_path(), 'session', strategy_name)
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

    def first_conversation(self, data: first_conversation_data):

        h5_ai_update_status(data.position_id, ENUM_H5_AI_STATUS.CHATTING)
        run_id = uuid4().hex[:12]
        logger.info(
            f"[初次会话] run_id={run_id} stage=service_start "
            f"conversation_mode={data.conversation_mode} account_count={len(data.inject_session.cookies_file_name_list)}"
        )

        manger = Manger()

        current_row = 0

        excel_file_path = None
        if data.conversation_mode == 'upload':
            uploaded_excel_path = resolve_excel_path(data.excel_file_name_list[0])
            result_dir = get_excel_result_dir()
            result_dir.mkdir(parents=True, exist_ok=True)
            result_path = result_dir / (
                f'{uploaded_excel_path.stem}_result_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{run_id}'
                f'{uploaded_excel_path.suffix}'
            )
            shutil.copy2(uploaded_excel_path, result_path)
            excel_file_path = str(result_path)
            logger.info(
                f'[Excel结果] run_id={run_id} stage=created '
                f'source={uploaded_excel_path} result={excel_file_path}'
            )

        for cookies_file_name in data.inject_session.cookies_file_name_list:

            cookies_file_path = str(resolve_cookie_path(cookies_file_name))

            logger.info(f'cookies地址为{cookies_file_path}')

            if data.conversation_mode == 'single':

                # 抽取策略
                search_condition_list = self.get_search_condition(data)

                manger.first_conversation_count = 0
                for search_condition in search_condition_list:
                    if manger.first_conversation_count >= data.limit_count:
                        logger.info('会话数超出限制')
                        break

                    if manger.pay_flag:
                        logger.info('账号发送次数超出')
                        break

                    manger.first_conversation(cookies_file_path,search_condition,data.limit_count,data.position_id)

            else:
                df = pd.read_excel(excel_file_path, sheet_name=0)
                logger.info(
                    f"[初次会话] run_id={run_id} stage=excel_resolved "
                    f"file={excel_file_path} total_rows={df.shape[0]}"
                )
                while current_row < df.shape[0]:
                    current_row,check_flag = manger.first_conversation_by_excel(
                        cookies_file_path,
                        excel_file_path,
                        current_row,
                        run_id=run_id,
                    )
                    if check_flag:
                        break

                logger.info(f'发起会话数：{manger.first_conversation_count}')
                logger.info(
                    f'[Excel结果] run_id={run_id} stage=account_finish '
                    f'file={excel_file_path} current_row={current_row}'
                )

            logger.info(
                f'[初次会话] 服务层结束 position_id={data.position_id} limit={data.limit_count} '
                f'成功开聊={manger.first_conversation_count} pay_flag={manger.pay_flag} cookies={cookies_file_name}'
            )
            logger.info(f"初次会话发起完毕,{cookies_file_name}结束完成")

        logger.info(f"[初次会话] run_id={run_id} stage=service_finish")

    def _get_strategies_by_filenames(self,filenames:list[str])->list[SearchCondition]:
        strategies : list[SearchCondition] = []
        for filename in filenames:
            strategy_path = os.path.join(get_save_path(),'session',filename)
            strategy = SearchCondition.from_json_file(strategy_path)
            strategies.append(strategy)
        return strategies
    def _get_strategies_by_sids(self,pid:int,sids:list[int])->list[SearchCondition]:
        strategies: list[SearchCondition] = []
        for sid in sids:
            res = get_search_conditions(pid,sid)
            data = get_ah_result_dict(res)
            strategy_str = data['result'][0]['strategy']
            strategy = SearchCondition.from_json_str(strategy_str)
            strategies.append(strategy)
        return strategies

    # def upload_screening(self, data: upload_screening_data):
    #     # 设置 ai 状态，变成初筛上传中
    #     h5_ai_update_status(data.position_id, ENUM_H5_AI_STATUS.RESUME_UPLOADING)
    #     manger = Manger()
    #     for cookies_file_name in data.cookies_file_name_list:
    #         cookies_file_path = os.path.join(get_save_path(), 'cookies', cookies_file_name)
    #         logger.info(f'cookies地址为{cookies_file_path}')
    #         if data.strategy_names:
    #             strategies = self._get_strategies_by_filenames(data.strategy_names)
    #         elif data.sids:
    #             strategies = self._get_strategies_by_sids(data.pid,data.sids)
    #         else:
    #             strategies = []
    #         for search_condition in strategies:
    #             manger.upload_screening_resume(cookies_file_path,search_condition,data.pid,data.hid)
    #         logger.info(f"上传高潜成功,{cookies_file_name}结束完成")
