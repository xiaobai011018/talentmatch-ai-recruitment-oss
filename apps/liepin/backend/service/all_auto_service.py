import time
from datetime import datetime

from backend.model.all_auto_data import all_auto_data
import copy

from backend.model.first_conversation_data import first_conversation_data
from backend.model.reply_model import reply_model
from backend.model.save_resume_data import save_resume_data
from backend.model.upload_screening_data import upload_screening_data
from backend.service.SearchConditionService import SearchConditionService
from backend.service.conversation_service import conversation_service


class all_auto_service:
    def all_auto(self, data: all_auto_data):
        search_condition = SearchConditionService()
        # if 'uploadScreening' in data.selected_process:
            # upload_screening_resume = upload_screening_data(
            #     hunterId=data.hunter_id,
            #     position_id=data.position_id,
            #     positionName=data.position_name,
            #     inject_session=data.inject_session
            # )
            # search_condition.upload_screening(upload_screening_resume)

        if 'firstConversation' in data.selected_process:
            first_conversation = first_conversation_data(
                limit_count=data.limit_count,
                position_id=data.position_id,
                conversation_mode=data.conversation_mode,
                excel_file_name_list=data.excel_file_name_list,
                inject_session=data.inject_session
            )
            search_condition.first_conversation(first_conversation)

        conversation = conversation_service()

        reply = reply_model(
            reply_mode=data.reply_mode,
            position_id=data.position_id,
            cookies_file_name_list=copy.deepcopy(data.inject_session.cookies_file_name_list),
            hunter_mode=data.hunter_mode
        )

        if 'secondConversation' in data.selected_process:
            conversation.start_second_conversation(reply)

        if 'autoReply' in data.selected_process:
            conversation.start_auto_reply(reply)

        if 'saveResume' in data.selected_process:

            save_resume_time = datetime.strptime(data.save_resume_time, "%Y-%m-%d %H:%M:%S")

            while datetime.now() < save_resume_time:
                time.sleep(10)

            conversation.stop_auto_reply()

            kwargs = {
                "reply_mode": data.reply_mode,
                "start_time": data.start_time,
                "end_time": data.end_time,
                "position_id": data.position_id,
                "cookies_file_name_list": copy.deepcopy(data.inject_session.cookies_file_name_list),
                "hunter_mode": data.hunter_mode,
                "fs_cookies_file_name": data.fs_cookies_file_name,
                "fs_position_name": data.fs_position_name
            }
            if data.hunter_mode:
                kwargs['son_position_id_list'] = data.son_position_id_list

            save_resume = save_resume_data(**kwargs)

            conversation.start_save_resume(save_resume)

        return
