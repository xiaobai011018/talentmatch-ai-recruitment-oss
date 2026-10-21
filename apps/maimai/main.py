"""
@describe:
@fileName: main.py
@time    : 2025/9/17 13:48
@author  : duke
"""

import argparse
import os.path
import logging

from werkzeug.utils import secure_filename

import src
from flask import Flask, render_template, request
import webbrowser
import json
import traceback
from copy import deepcopy
import pickle
import atexit
import signal
import threading

from src.service.ah_service import ah_service

parser = argparse.ArgumentParser()
parser.add_argument('--dev', '-d', action='store_true')
parser.add_argument('--no-frontend', action='store_true')
args_main = parser.parse_args()

if args_main.dev:
    src._CONFIG['dev'] = True

from src import *

logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__,
            static_folder=WEB_PATH,  # 设置静态文件夹目录
            template_folder=WEB_PATH,
            static_url_path='')  # 设置vue编译输出目录dist文件夹，为Flask模板文件目录

manager: src.Manager = None
if os.path.exists(SAVE_PATH):
    try:
        with open(SAVE_PATH, 'rb') as f:
            manager = pickle.load(f)
    except:
        if src._CONFIG['dev']:
            raise
        else:
            manager = src.Manager()
else:
    manager = src.Manager()

if not os.path.exists(SAVE_FILE_DIR):
    os.mkdir(SAVE_FILE_DIR)


def on_atexit():
    global manager

    manager.logger.active()

    with open(SAVE_PATH, 'wb') as f:
        pickle.dump(manager, f)

    print('pickle succeed')


atexit.register(on_atexit)


@app.route('/')
def index():
    return render_template('index.html', name='index')

@app.route('/cmd_save_resume', methods=['GET'])
def cmd_save_resume():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        args = request.args
        user_ids = list(map(int, args['user_ids'].split(',')))
        reply_mode = args.get('reply_mode', 'all')
        position_id = args.get('position_id') or args.get('pid')
        if reply_mode == 'single' and not position_id:
            raise ValueError('单独岗位保存需要 position_id')

        data = manager.save_resume(
            reply_mode=reply_mode,
            start_time=args['start_time'],
            end_time=args['end_time'],
            position_id=position_id,
            user_ids=user_ids,
        )
        resp['data'] = data
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
    return resp


@app.route('/cmd_auto_process_all', methods=['GET'])
def cmd_auto_process_all():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    args = request.args
    try:
        manager.auto_process_all(**args)
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp

@app.route('/login_by_chrome', methods=['GET'])
def login_by_chrome():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        manager.login_by_chrome()
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp

def _parse_user_ids(args):
    raw = args.get('user_ids', '').strip()
    if not raw:
        return None
    return list(map(int, raw.split(',')))


@app.route('/cmd_auto_reply', methods=['GET'])
def cmd_auto_reply():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    args = request.args
    try:
        if manager.is_auto_reply():
            resp['succeed'] = True
            resp['data'] = '自动回复已在运行'
            return resp
        user_ids = _parse_user_ids(args)
        threading.Thread(
            target=manager.process_auto_reply,
            kwargs={'user_ids': user_ids},
            daemon=True,
        ).start()
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/cmd_stop_auto_reply', methods=['GET'])
def cmd_stop_auto_reply():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        manager.stop_auto_reply()
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/cmd_upload_resume', methods=['GET'])
def cmd_upload_resume():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        resp['data'] = manager.process_upload_resume()
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/is_auto_reply', methods=['GET'])
def is_auto_reply():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        resp['data'] = manager.is_auto_reply()
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/cmd_second_contact', methods=['GET'])
def cmd_second_contact():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    args = request.args
    user_ids = list(map(int, args['user_ids'].split(',')))
    reply_mode = args.get('reply_mode', 'all')
    position_id = args.get('position_id')
    try:
        if reply_mode == 'single' and not position_id:
            raise ValueError('单独岗位二次激活需要 position_id')
        resp['data'] = manager.second_contact(
            user_ids=user_ids,
            reply_mode=reply_mode,
            position_id=position_id,
        )
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/is_locked', methods=['GET'])
def is_locked():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        resp['data'] = manager.is_locked()
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/cmd_first_contact', methods=['GET'])
def cmd_first_contact():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        args = request.args
        pid = args['pid']
        search_condition_ids = list(map(int, args['search_condition_ids'].split(',')))
        greet_text = args['greet_text']
        limit_per_user = int(args['limit_per_user'])
        user_ids = list(map(int, args['user_ids'].split(',')))

        succ_count, search_total, exceptions = manager.first_contact(pid, search_condition_ids, greet_text,
                                                                        limit_per_user=limit_per_user,
                                                                        user_ids=user_ids)
        resp['data'] = {
            'succ_count': succ_count,
            'search_total': search_total,
            'exceptions': list(map(str, exceptions)),
        }
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp

@app.route('/cmd_first_contact_excel', methods=['GET'])
def cmd_first_contact_excel():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        args = request.args
        excel_name = args['excel_name']
        greet_text = args['greet_text']
        limit_per_user = int(args['limit_per_user'])
        user_ids = list(map(int, args['user_ids'].split(',')))

        excel_path = os.path.join(RSC_DIR,excel_name)

        succ_count, search_total, exceptions = manager.first_contact_with_excel(excel_path, greet_text,
                                                                        limit_per_user=limit_per_user,
                                                                        user_ids=user_ids)
        resp['data'] = {
            'succ_count': succ_count,
            'search_total': search_total,
            'exceptions': list(map(str, exceptions)),
        }
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp

@app.route('/upload_excel',methods = ['POST'])
def upload_excel():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        f = request.files.get('file')
        filename = secure_filename(f.filename or "")
        os.makedirs(RSC_DIR, exist_ok=True)
        excel_save_path = os.path.join(RSC_DIR,filename)
        f.save(excel_save_path)
        resp['succeed'] = True
        resp['data'] = {}
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/update_user', methods=['POST'])
def update_user():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        cookies = json.loads(request.data)
        uid = manager.update_user(cookies)
        resp['succeed'] = True
        resp['data'] = {'uid': uid}
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/get_users', methods=['GET'])
def get_user():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        users = manager.get_users()
        resp['data'] = [user.__dict__ for user in users]
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/get_cookies', methods=['GET'])
def get_cookies():
    resp = deepcopy(TEMPLATE_FLASK_RESP)
    try:
        cookies = manager.export_cookies()
        for key, val in cookies.items():
            with open(os.path.join(SAVE_FILE_DIR, f'{key}_cookies.json'), 'w') as f:
                f.write(json.dumps(val))
        resp['data'] = cookies
        resp['succeed'] = True
    except Exception as e:
        resp['data'] = str(e)
        if args_main.dev:
            resp['data'] = traceback.format_exc()
            traceback.print_exc()
            # raise
    return resp


@app.route('/shutdown', methods=['GET'])
def shutdown():
    on_atexit()
    os.kill(os.getpid(), signal.SIGINT)

ah_service = ah_service()
@app.route("/ah_search/hunter",methods=['GET'])
def search_hunter():
    try:
        keyword = request.args.get('keyword', '').strip()
        hunter_list = ah_service.search_hunter_list(keyword)
        return hunter_list
    except Exception as e:
        traceback.print_exc()

@app.route("/ah_search/position",methods=['GET'])
def search_position():
    try:
        keyword = request.args.get('keyword', '').strip()
        hid = request.args.get("hid",'').strip()
        position_list = ah_service.search_position_list(hid,keyword)
        return position_list
    except Exception as e:
        traceback.print_exc()

@app.route("/ah_search/strategy",methods=['GET'])
def search_strategy():
    try:
        keyword = request.args.get('keyword', '').strip()
        pid = request.args.get("pid",'').strip()
        strategy_list = ah_service.search_strategy_list(pid,keyword)
        return strategy_list
    except Exception as e:
        traceback.print_exc()

if __name__ == '__main__':
    print(f'网页控制台在: http://127.0.0.1:{PORT}')

    if not args_main.no_frontend:
        webbrowser.open(f'http://127.0.0.1:{PORT}')

    app.run(
        debug=False,  # 调试
        host='0.0.0.0',  # ip
        port=PORT,  # 端口
        # ssl_context='adhoc',  # 默认SSL证书，实现https
        threaded=True,  # 多线程
    )
