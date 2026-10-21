import time
from datetime import datetime

from backend.core.model.all_auto_data import all_auto_data
import copy

from backend.core.model.first_conversation_data import first_conversation_data
from backend.core.model.first_conversation_with_excel_data import first_conversation_with_excel_data
from backend.core.model.reply_model import reply_model
from backend.core.model.save_resume_data import save_resume_data
from backend.core.model.upload_screening_data import upload_screening_data
from backend.core.router.search_condition_router import first_conversation_with_excel
from backend.core.service.SearchConditionService import SearchConditionService
from backend.core.service.conversation_service import conversation_service


class all_auto_service:
    def all_auto(self, data:all_auto_data):
        search_service = SearchConditionService()
        conversation = conversation_service()
        if 'uploadScreening' in data.selected_process:
            upload_screening = upload_screening_data(
                hunterId=data.hunter_id,
                position_id=data.position_id,
                positionName= data.position_name,
                inject_session=copy.deepcopy(data.inject_session)
            )
            search_service.upload_screening(upload_screening)

        reply = reply_model(
            reply_mode=data.reply_mode,
            position_id=data.position_id,
            cookies_file_name_list=copy.deepcopy(data.inject_session.cookies_file_name_list)
        )
        if 'firstConversation' in data.selected_process:
            first_conversation = first_conversation_data(
                limit_count=data.limit_count,
                position_id=data.position_id,
                inject_session=copy.deepcopy(data.inject_session)
            )

            search_service.first_conversation(first_conversation)

        if 'first_conversation_with_excel' in data.selected_process:
            first_conversation_with_excel = first_conversation_with_excel_data(
                limit_count=data.limit_count,
                excel_name=data.excel_name,
                cookies_file_name_list=data.cookies_file_name_list
            )
            search_service.first_conversation_with_excel(first_conversation_with_excel)

        if 'secondConversation' in data.selected_process:
            conversation.start_second_conversation(reply)

        if 'autoReply' in data.selected_process:
            conversation.start_auto_reply(reply)

        if 'saveResume' in data.selected_process:

            save_resume_time = datetime.strptime(data.save_resume_time, "%Y-%m-%d %H:%M:%S")

            while datetime.now() < save_resume_time:
                time.sleep(10)

            conversation.stop_auto_reply()

            save_resume = save_resume_data(
                reply_mode=data.reply_mode,
                start_time=data.start_time,
                end_time=data.end_time,
                recommend_id=data.hunter_id,
                position_id=data.position_id,
                cookies_file_name_list=copy.deepcopy(data.inject_session.cookies_file_name_list)
            )

            conversation.start_save_resume(save_resume)

        return




