from src.io.anyhelper import *
class ah_service():
    def __init__(self):
        pass
    def search_hunter_list(self,keyword:str):
        all_hunter_list = get_headhunter_list('all').json()['results'] + get_headhunter_list('clients').json()['results']
        if not keyword:
            return all_hunter_list
        filter_user_list =[]

        for hunter in all_hunter_list:
            if keyword.lower() in hunter['Name'].lower():
                filter_user_list.append(hunter)
                continue
            if keyword.lower() in str(hunter['user_id']):
                filter_user_list.append(hunter)
                continue
        return filter_user_list

    def search_position_list(self,hid,keyword:str):
        position_list = get_position_list(hid).json()['results']
        if not keyword:
            return position_list
        filter_position_list =[]
        search_filed_list = [
            'position_id',
            'position_name'
            'company_name'
        ]

        for position in position_list:
            for search_filed in search_filed_list:
                if keyword.lower() in str(position.get(search_filed,'')):
                    filter_position_list.append(position)
                    break
        return filter_position_list

    def search_strategy_list(self, pid,keyword):
        strategy_list = get_search_condition(pid).json()['results']
        if not keyword:
            return strategy_list
        filter_strategy_list = []
        search_filed_list = [
            'id',
            'name',
            'user_id'
        ]
        for strategy in strategy_list:
            for search_filed in search_filed_list:
                if keyword.lower() in str(strategy.get(search_filed,'')):
                    filter_strategy_list.append(strategy)
                    break
        return filter_strategy_list