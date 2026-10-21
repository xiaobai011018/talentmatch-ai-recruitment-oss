import os.path
import sys

class path_util:
    @classmethod
    def get_root_path(cls):
        if getattr(sys,'frozen',False):
            BASE_DIR = sys._MEIPASS
        else:
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return BASE_DIR

    @classmethod
    def get_save_path(cls):
        root_path = cls.get_root_path()
        if getattr(sys,'frozen',False):
            save_path = os.path.join(os.path.dirname(root_path),'save')
        else:
            save_path = os.path.join(root_path,'save')
        return save_path

    @classmethod
    def get_backend_path(cls):
        root_path = cls.get_root_path()
        backend_path = os.path.join(root_path,'backend')
        return backend_path

    @classmethod
    def get_core_path(cls):
        backend_path = cls.get_backend_path()
        core_path = os.path.join(backend_path,'core')
        return core_path

    @classmethod
    def get_frontend_path(cls):
        root_path = cls.get_root_path()
        frontend_path = os.path.join(root_path,'frontend')
        return frontend_path

    @classmethod
    def get_config_path(cls):
        core_path = cls.get_core_path()
        config_path = os.path.join(core_path,'config')
        return config_path

    @classmethod
    def get_dict_path(cls):
        frontend_path = cls.get_frontend_path()
        dict_path = os.path.join(frontend_path,'dist')
        return dict_path

    @classmethod
    def get_cookies_path(cls):
        save_path = cls.get_save_path()
        cookies_path = os.path.join(save_path,'cookies')
        return cookies_path

    @classmethod
    def get_session_path(cls):
        save_path = cls.get_save_path()
        session_path = os.path.join(save_path,'session')
        return session_path

    @classmethod
    def get_resource_path(cls):
        core_path = cls.get_core_path()
        resource_path = os.path.join(core_path,'resource')
        return resource_path

    @classmethod
    def get_excel_path(cls):
        save_path = cls.get_save_path()
        excel_path = os.path.join(save_path,'excel')
        return excel_path