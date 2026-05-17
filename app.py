import os
import json
import logging
import glob
import time
import subprocess
import sys
import socket
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, request, jsonify
from flask_compress import Compress
from functools import wraps
from threading import Lock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FOLDER = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_FOLDER, exist_ok=True)

def setup_logger():
    logger = logging.getLogger('app_manager')
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    log_file = os.path.join(LOG_FOLDER, 'app.log')

    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.suffix = '%Y-%m-%d'

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def cleanup_old_logs():
    logger = logging.getLogger('app_manager')
    cutoff_date = datetime.now() - timedelta(days=7)
    log_pattern = os.path.join(LOG_FOLDER, 'app.log*')

    for old_log in glob.glob(log_pattern):
        try:
            log_time = datetime.fromtimestamp(os.path.getmtime(old_log))
            if log_time < cutoff_date:
                os.remove(old_log)
                logger.info(f'Removed old log file: {old_log}')
        except Exception as e:
            print(f'Error removing old log {old_log}: {e}')

    for i in range(1, 8):
        log_file = os.path.join(LOG_FOLDER, f'app.log.{(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")}')
        if os.path.exists(log_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            if file_time < cutoff_date:
                try:
                    os.remove(log_file)
                    logger.info(f'Removed expired log: {log_file}')
                except Exception as e:
                    print(f'Error removing expired log {log_file}: {e}')

logger = setup_logger()
cleanup_old_logs()

app = Flask(__name__)
Compress(app)

running_processes = {
    'http': None,
    'https': None,
    'ftp': None,
    'webdav': None,
    'webdav_https': None,
    'samba': None
}

CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'config.json')

DEFAULT_CONFIG = {
    'port': 8080,
    'https_port': 8443,
    'https_enabled': False,
    'webdav_enabled': False,
    'webdav_port': 5001,
    'webdav_https_enabled': False,
    'webdav_https_port': 5002,
    'username': 'admin',
    'password': '123456',
    'network_name': 'Local_Pan',
    'network_logo': '',
    'ssl_crt': '',
    'ssl_key': '',
    'copyright_year': '',
    'copyright_domain': '',
    'samba_enabled': False,
    'samba_port': 445,
    'ftp_enabled': False,
    'ftp_port': 21,
    'ftp_passive_min': 50000,
    'ftp_passive_max': 50050
}

_config_cache = {}
_config_last_load = 0
_config_lock = Lock()
_CONFIG_CACHE_TTL = 30

def load_config():
    global _config_cache, _config_last_load
    now = time.time()
    if now - _config_last_load > _CONFIG_CACHE_TTL:
        config_needs_save = False
        with _config_lock:
            if now - _config_last_load > _CONFIG_CACHE_TTL:
                if os.path.exists(CONFIG_FILE):
                    try:
                        with open(CONFIG_FILE, 'r') as f:
                            _config_cache = json.load(f)
                    except Exception:
                        _config_cache = DEFAULT_CONFIG.copy()
                else:
                    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
                    _config_cache = DEFAULT_CONFIG.copy()
                    config_needs_save = True
                _config_last_load = now
        if config_needs_save:
            save_config(_config_cache)
    return _config_cache.copy()

def save_config(config_data):
    global _config_cache, _config_last_load
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)
    with _config_lock:
        _config_cache = config_data.copy()
        _config_last_load = time.time()

def is_port_available(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.bind(('0.0.0.0', port))
            return True
    except OSError:
        return False

def stop_process(process):
    if process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=3)
            return True
        except Exception as e:
            logger.error(f'Error stopping process: {str(e)}')
            try:
                process.kill()
            except:
                pass
            return False
    return True

def stop_all_services():
    for service_name, process in running_processes.items():
        if process:
            stop_process(process)
            running_processes[service_name] = None
            logger.info(f'{service_name} service stopped')

def start_service(service_name):
    config = load_config()
    sub_py_dir = os.path.join(BASE_DIR, 'sub_py')

    cmd = None

    if service_name == 'http':
        cmd = [sys.executable, os.path.join(sub_py_dir, 'web_server.py'), '--mode', 'http']
    elif service_name == 'https':
        if not config.get('https_enabled'):
            return False
        ssl_crt = config.get('ssl_crt', '')
        ssl_key = config.get('ssl_key', '')
        ssl_crt_path = os.path.join(BASE_DIR, ssl_crt) if ssl_crt else ''
        ssl_key_path = os.path.join(BASE_DIR, ssl_key) if ssl_key else ''
        if not ssl_crt_path or not ssl_key_path or not os.path.exists(ssl_crt_path) or not os.path.exists(ssl_key_path):
            logger.warning('HTTPS not started - SSL cert/key not configured properly')
            config['https_enabled'] = False
            save_config(config)
            return False
        cmd = [sys.executable, os.path.join(sub_py_dir, 'web_server.py'), '--mode', 'https']
    elif service_name == 'ftp':
        if not config.get('ftp_enabled'):
            return False
        cmd = [sys.executable, os.path.join(sub_py_dir, 'ftp_server.py')]
    elif service_name == 'webdav':
        if not config.get('webdav_enabled'):
            return False
        cmd = [sys.executable, os.path.join(sub_py_dir, 'webdav_server.py')]
    elif service_name == 'webdav_https':
        if not config.get('webdav_https_enabled'):
            return False
        ssl_crt = config.get('ssl_crt', '')
        ssl_key = config.get('ssl_key', '')
        ssl_crt_path = os.path.join(BASE_DIR, ssl_crt) if ssl_crt else ''
        ssl_key_path = os.path.join(BASE_DIR, ssl_key) if ssl_key else ''
        if not ssl_crt_path or not ssl_key_path or not os.path.exists(ssl_crt_path) or not os.path.exists(ssl_key_path):
            logger.warning('WebDAV HTTPS not started - SSL cert/key not configured properly')
            return False
        cmd = [sys.executable, os.path.join(sub_py_dir, 'webdav_server.py'), '--ssl']
    elif service_name == 'samba':
        if not config.get('samba_enabled'):
            return False
        cmd = [sys.executable, os.path.join(sub_py_dir, 'samba_server.py')]
    else:
        logger.error(f'Unknown service: {service_name}')
        return False

    if cmd is None:
        return False

    try:
        env = os.environ.copy()
        if sys.platform == 'win32':
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = subprocess.SW_HIDE
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008
            process = subprocess.Popen(
                cmd,
                env=env,
                startupinfo=startup_info,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            si = open('/dev/null', 'r')
            so = open('/dev/null', 'w')
            se = open('/dev/null', 'w')
            process = subprocess.Popen(
                cmd,
                env=env,
                stdin=si,
                stdout=so,
                stderr=se,
                start_new_session=True
            )
            si.close()
            so.close()
            se.close()

        running_processes[service_name] = process
        logger.info(f'{service_name} service started with PID {process.pid}')
        
        if service_name == 'https':
            time.sleep(1)
            if process.poll() is not None:
                logger.error('HTTPS service failed to start - process exited immediately')
                running_processes[service_name] = None
                config = load_config()
                config['https_enabled'] = False
                save_config(config)
                return False
                
        return True
    except Exception as e:
        logger.error(f'Failed to start {service_name} service: {str(e)}')
        if service_name == 'https':
            config = load_config()
            config['https_enabled'] = False
            save_config(config)
        return False

def restart_service(service_name):
    if running_processes[service_name]:
        stop_process(running_processes[service_name])
    config = load_config()
    return start_service(service_name)

def restart_service_with_config(service_name):
    stop_process(running_processes[service_name])
    running_processes[service_name] = None
    config = load_config()
    return start_service(service_name)

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'GET':
        config_data = load_config()
        ssl_crt_path = os.path.join(BASE_DIR, config_data.get('ssl_crt', '')) if config_data.get('ssl_crt') else ''
        ssl_key_path = os.path.join(BASE_DIR, config_data.get('ssl_key', '')) if config_data.get('ssl_key') else ''
        ssl_enabled = bool(config_data.get('https_enabled') and ssl_crt_path and ssl_key_path and os.path.exists(ssl_crt_path) and os.path.exists(ssl_key_path))

        return jsonify({
            'port': config_data.get('port'),
            'https_port': config_data.get('https_port'),
            'https_enabled': config_data.get('https_enabled'),
            'https_available': ssl_enabled,
            'webdav_enabled': config_data.get('webdav_enabled'),
            'webdav_port': config_data.get('webdav_port'),
            'webdav_https_enabled': config_data.get('webdav_https_enabled'),
            'webdav_https_port': config_data.get('webdav_https_port'),
            'username': config_data.get('username'),
            'network_name': config_data.get('network_name'),
            'network_logo': config_data.get('network_logo'),
            'ssl_crt': config_data.get('ssl_crt'),
            'ssl_key': config_data.get('ssl_key'),
            'copyright_year': config_data.get('copyright_year'),
            'copyright_domain': config_data.get('copyright_domain'),
            'samba_enabled': config_data.get('samba_enabled'),
            'samba_port': config_data.get('samba_port'),
            'ftp_enabled': config_data.get('ftp_enabled'),
            'ftp_port': config_data.get('ftp_port'),
            'ftp_passive_min': config_data.get('ftp_passive_min'),
            'ftp_passive_max': config_data.get('ftp_passive_max')
        })
    else:
        data = request.get_json()
        config_data = load_config()

        new_port = data.get('port')
        new_https_port = data.get('https_port')
        https_enabled = data.get('https_enabled', False)
        webdav_enabled = data.get('webdav_enabled', False)
        webdav_port = data.get('webdav_port')
        webdav_https_enabled = data.get('webdav_https_enabled', False)
        webdav_https_port = data.get('webdav_https_port')
        samba_enabled = data.get('samba_enabled', False)
        samba_port = data.get('samba_port')
        ftp_enabled = data.get('ftp_enabled', False)
        ftp_port = data.get('ftp_port')
        ftp_passive_min = data.get('ftp_passive_min')
        ftp_passive_max = data.get('ftp_passive_max')
        username = data.get('username')
        password = data.get('password')
        ssl_crt = data.get('ssl_crt', '')
        ssl_key = data.get('ssl_key', '')
        network_logo = data.get('network_logo', '')

        ssl_crt_path = os.path.join(BASE_DIR, ssl_crt) if ssl_crt else ''
        ssl_key_path = os.path.join(BASE_DIR, ssl_key) if ssl_key else ''

        if https_enabled:
            if not new_https_port:
                return jsonify({'error': 'https_port_required', 'message': '启用HTTPS需要填写HTTPS端口'}), 400
            if not ssl_crt:
                return jsonify({'error': 'ssl_crt_required', 'message': '启用HTTPS需要填写SSL证书路径'}), 400
            if not ssl_key:
                return jsonify({'error': 'ssl_key_required', 'message': '启用HTTPS需要填写SSL密钥路径'}), 400
            if ssl_crt_path and not os.path.exists(ssl_crt_path):
                return jsonify({'error': 'ssl_crt_not_exists', 'message': 'SSL证书文件不存在'}), 400
            if ssl_key_path and not os.path.exists(ssl_key_path):
                return jsonify({'error': 'ssl_key_not_exists', 'message': 'SSL密钥文件不存在'}), 400

        if webdav_https_enabled:
            if not ssl_crt or not ssl_key:
                return jsonify({'error': 'ssl_required', 'message': '启用HTTPS WebDAV需要SSL证书'}), 400

        services_to_restart = []

        if new_port is not None and new_port != config_data.get('port'):
            if not is_port_available(new_port):
                return jsonify({'error': 'port_in_use', 'message': 'HTTP端口被占用'}), 400
            services_to_restart.append('http')

        if https_enabled != config_data.get('https_enabled'):
            if https_enabled:
                services_to_restart.append('https')
            else:
                services_to_restart.append('https')

        if new_https_port is not None and new_https_port != config_data.get('https_port'):
            if not is_port_available(new_https_port):
                return jsonify({'error': 'https_port_in_use', 'message': 'HTTPS端口被占用'}), 400
            services_to_restart.append('https')

        if webdav_enabled != config_data.get('webdav_enabled'):
            services_to_restart.append('webdav')

        if webdav_port is not None and webdav_port != config_data.get('webdav_port'):
            services_to_restart.append('webdav')

        if webdav_https_enabled != config_data.get('webdav_https_enabled'):
            if webdav_https_enabled:
                services_to_restart.append('webdav_https')
            else:
                services_to_restart.append('webdav_https')

        if webdav_https_port is not None and webdav_https_port != config_data.get('webdav_https_port'):
            services_to_restart.append('webdav_https')

        if samba_enabled != config_data.get('samba_enabled'):
            services_to_restart.append('samba')

        if samba_port is not None and samba_port != config_data.get('samba_port'):
            services_to_restart.append('samba')

        if ftp_enabled != config_data.get('ftp_enabled'):
            services_to_restart.append('ftp')

        if ftp_port is not None and ftp_port != config_data.get('ftp_port'):
            services_to_restart.append('ftp')

        if username is not None and username != config_data.get('username'):
            services_to_restart.extend(['ftp', 'samba', 'webdav', 'webdav_https', 'http', 'https'])

        if password is not None and password != config_data.get('password'):
            services_to_restart.extend(['ftp', 'samba', 'webdav', 'webdav_https', 'http', 'https'])

        if ssl_crt != config_data.get('ssl_crt') or ssl_key != config_data.get('ssl_key'):
            if https_enabled or webdav_https_enabled:
                services_to_restart.extend(['https', 'webdav_https'])

        config_data['port'] = new_port if new_port is not None else config_data.get('port')
        config_data['https_port'] = new_https_port if new_https_port is not None else config_data.get('https_port')
        config_data['https_enabled'] = https_enabled
        config_data['webdav_enabled'] = webdav_enabled
        config_data['webdav_port'] = webdav_port if webdav_port is not None else config_data.get('webdav_port')
        config_data['webdav_https_enabled'] = webdav_https_enabled
        config_data['webdav_https_port'] = webdav_https_port if webdav_https_port is not None else config_data.get('webdav_https_port')
        config_data['username'] = username if username is not None else config_data.get('username')
        config_data['password'] = password if password is not None else config_data.get('password')
        config_data['ssl_crt'] = ssl_crt
        config_data['ssl_key'] = ssl_key
        config_data['network_name'] = data.get('network_name', config_data.get('network_name'))
        config_data['network_logo'] = network_logo
        config_data['copyright_year'] = data.get('copyright_year', config_data.get('copyright_year'))
        config_data['copyright_domain'] = data.get('copyright_domain', config_data.get('copyright_domain'))
        config_data['samba_enabled'] = samba_enabled
        config_data['samba_port'] = samba_port if samba_port is not None else config_data.get('samba_port')
        config_data['ftp_enabled'] = ftp_enabled
        config_data['ftp_port'] = ftp_port if ftp_port is not None else config_data.get('ftp_port')
        config_data['ftp_passive_min'] = ftp_passive_min if ftp_passive_min is not None else config_data.get('ftp_passive_min')
        config_data['ftp_passive_max'] = ftp_passive_max if ftp_passive_max is not None else config_data.get('ftp_passive_max')

        save_config(config_data)

        for service in set(services_to_restart):
            restart_service_with_config(service)

        return jsonify({
            'success': True,
            'services_restarted': list(set(services_to_restart))
        })

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({
        'http': {
            'running': running_processes['http'] is not None and running_processes['http'].poll() is None
        },
        'https': {
            'enabled': load_config().get('https_enabled', False),
            'running': running_processes['https'] is not None and running_processes['https'].poll() is None
        },
        'ftp': {
            'enabled': load_config().get('ftp_enabled', False),
            'running': running_processes['ftp'] is not None and running_processes['ftp'].poll() is None
        },
        'webdav': {
            'enabled': load_config().get('webdav_enabled', False),
            'running': running_processes['webdav'] is not None and running_processes['webdav'].poll() is None
        },
        'webdav_https': {
            'enabled': load_config().get('webdav_https_enabled', False),
            'running': running_processes['webdav_https'] is not None and running_processes['webdav_https'].poll() is None
        },
        'samba': {
            'enabled': load_config().get('samba_enabled', False),
            'running': running_processes['samba'] is not None and running_processes['samba'].poll() is None
        }
    })

@app.route('/api/restart-service', methods=['POST'])
def api_restart_service():
    data = request.get_json()
    service_name = data.get('service', '')

    valid_services = ['http', 'https', 'ftp', 'webdav', 'webdav_https', 'samba']

    if service_name not in valid_services:
        return jsonify({'error': 'invalid_service', 'message': f'无效的服务名称'}), 400

    success = restart_service_with_config(service_name)

    return jsonify({
        'success': success,
        'service': service_name,
        'message': f'{service_name}服务已重启' if success else f'{service_name}服务重启失败'
    })

@app.route('/api/restart', methods=['POST'])
def api_restart():
    def do_restart():
        stop_all_services()
        time.sleep(0.5)
        args = [sys.executable] + sys.argv
        env = os.environ.copy()
        if sys.platform == 'win32':
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = subprocess.SW_HIDE
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(args, env=env, startupinfo=startup_info, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            si = open('/dev/null', 'r')
            so = open('/dev/null', 'w')
            se = open('/dev/null', 'w')
            subprocess.Popen(args, env=env, stdin=si, stdout=so, stderr=se, start_new_session=True)
            si.close()
            so.close()
            se.close()
        os._exit(0)

    import threading
    threading.Thread(target=do_restart, daemon=False).start()
    return jsonify({'success': True})

@app.route('/api/check-port')
def api_check_port():
    port = request.args.get('port', type=int)
    if port is None:
        return jsonify({'error': 'port_required', 'message': '请提供端口号'}), 400
    
    if port < 1 or port > 65535:
        return jsonify({'available': False, 'reason': 'invalid_range', 'message': '端口号必须在1-65535之间'})
    
    available = is_port_available(port)
    return jsonify({
        'available': available,
        'port': port,
        'message': '端口可用' if available else '端口已被占用'
    })

@app.route('/api/public-config')
def public_config():
    config_data = load_config()
    return jsonify({
        'network_name': config_data.get('network_name', 'Local_Pan'),
        'network_logo': config_data.get('network_logo', ''),
        'copyright_year': config_data.get('copyright_year', ''),
        'copyright_domain': config_data.get('copyright_domain', '')
    })

if __name__ == '__main__':
    import threading

    logger.info('Application manager starting...')

    config = load_config()

    http_port = config.get('port', 8080)
    https_port = config.get('https_port', 8443)

    if config.get('https_enabled'):
        logger.info(f'HTTPS File Manager will run on https://0.0.0.0:{https_port}/')
        https_started = start_service('https')
        if not https_started:
            logger.warning('HTTPS service failed to start, falling back to HTTP')
            config = load_config()
            config['https_enabled'] = False
            save_config(config)
            logger.info(f'HTTP File Manager will run on http://0.0.0.0:{http_port}/')
            threading.Thread(target=lambda: start_service('http'), daemon=True).start()
        else:
            logger.info(f'HTTP File Manager will run on http://0.0.0.0:{http_port}/ (redirecting to HTTPS)')
            threading.Thread(target=lambda: start_service('http'), daemon=True).start()
    else:
        logger.info(f'HTTP File Manager will run on http://0.0.0.0:{http_port}/')
        threading.Thread(target=lambda: start_service('http'), daemon=True).start()

    if config.get('webdav_enabled'):
        webdav_port = config.get('webdav_port', 5001)
        logger.info(f'WebDAV service will run on http://0.0.0.0:{webdav_port}/webdav/')
        threading.Thread(target=lambda: start_service('webdav'), daemon=True).start()

    if config.get('webdav_https_enabled'):
        webdav_https_port = config.get('webdav_https_port', 5002)
        logger.info(f'WebDAV HTTPS service will run on https://0.0.0.0:{webdav_https_port}/webdav/')
        threading.Thread(target=lambda: start_service('webdav_https'), daemon=True).start()

    if config.get('ftp_enabled'):
        ftp_port = config.get('ftp_port', 21)
        logger.info(f'FTP service will run on ftp://0.0.0.0:{ftp_port}/')
        threading.Thread(target=lambda: start_service('ftp'), daemon=True).start()

    if config.get('samba_enabled'):
        samba_port = config.get('samba_port', 445)
        logger.info(f'Samba service will run on port {samba_port}')
        threading.Thread(target=lambda: start_service('samba'), daemon=True).start()

    logger.info('Management API server running on http://0.0.0.0:8088/')

    app.run(host='0.0.0.0', port=8088, debug=False)
