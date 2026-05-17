import os
import sys
import logging
from werkzeug.serving import run_simple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import get_config

def setup_logger(name='web_server'):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()

def create_flask_app():
    import json
    import mimetypes
    import hashlib
    import socket
    import glob
    import time
    from datetime import datetime, timedelta
    from logging.handlers import TimedRotatingFileHandler
    from flask import Flask, request, jsonify, send_file, send_from_directory, render_template, abort, redirect, url_for
    from flask_compress import Compress
    from functools import wraps

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOG_FOLDER = os.path.join(BASE_DIR, 'logs')
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    TEMPLATE_FOLDER = os.path.join(BASE_DIR, 'templates')
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    LOCKS_FILE = os.path.join(BASE_DIR, 'config', 'locks.json')
    SHARES_FILE = os.path.join(BASE_DIR, 'config', 'shares.json')
    CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'config.json')
    IMG_FOLDER = os.path.join(BASE_DIR, 'img')

    os.makedirs(LOG_FOLDER, exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.dirname(LOCKS_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(SHARES_FILE), exist_ok=True)
    os.makedirs(TEMPLATE_FOLDER, exist_ok=True)
    os.makedirs(STATIC_FOLDER, exist_ok=True)
    os.makedirs(IMG_FOLDER, exist_ok=True)

    app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
    
    Compress(app)

    app.logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    app.logger.addHandler(handler)

    _config_cache_data = {}
    _config_cache_last_load = 0
    _CONFIG_CACHE_TTL = 30

    def load_config():
        nonlocal _config_cache_data, _config_cache_last_load
        now = time.time()
        if now - _config_cache_last_load > _CONFIG_CACHE_TTL:
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, 'r') as f:
                        _config_cache_data = json.load(f)
                except Exception:
                    _config_cache_data = {}
            else:
                _config_cache_data = {}
            _config_cache_last_load = now
        return _config_cache_data.copy()

    def save_config(config_data):
        nonlocal _config_cache_data, _config_cache_last_load
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        _config_cache_data = config_data.copy()
        _config_cache_last_load = time.time()

    @app.before_request
    def redirect_to_https():
        config_data = load_config()
        if config_data.get('https_enabled') and request.scheme == 'http':
            https_port = config_data.get('https_port')
            path = request.full_path
            if path == '/?':
                path = '/'
            return redirect(f'https://{request.host.split(":")[0]}:{https_port}{path}', code=301)

    def load_locks():
        if os.path.exists(LOCKS_FILE):
            try:
                with open(LOCKS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_locks(locks):
        os.makedirs(os.path.dirname(LOCKS_FILE), exist_ok=True)
        with open(LOCKS_FILE, 'w') as f:
            json.dump(locks, f, indent=4)

    def is_path_locked(relative_path):
        locks = load_locks()
        if relative_path in locks:
            full_path = os.path.join(UPLOAD_FOLDER, relative_path.lstrip('/'))
            if not os.path.exists(full_path):
                return False
        return relative_path in load_locks()

    def set_path_locked(relative_path, locked=True):
        locks = load_locks()
        if locked:
            locks[relative_path] = True
        elif relative_path in locks:
            del locks[relative_path]
        save_locks(locks)

    def cleanup_invalid_locks():
        locks = load_locks()
        valid_locks = {}
        for relative_path in locks:
            full_path = os.path.join(UPLOAD_FOLDER, relative_path.lstrip('/'))
            if os.path.exists(full_path) and os.path.isdir(full_path):
                valid_locks[relative_path] = True
        if valid_locks != locks:
            save_locks(valid_locks)

    def load_shares():
        if os.path.exists(SHARES_FILE):
            try:
                with open(SHARES_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_shares(shares):
        os.makedirs(os.path.dirname(SHARES_FILE), exist_ok=True)
        with open(SHARES_FILE, 'w') as f:
            json.dump(shares, f, indent=4, ensure_ascii=False)

    def get_share_by_token(token):
        shares = load_shares()
        for share in shares:
            if share.get('token') == token:
                return share
        return None

    def add_or_update_share(token, path):
        shares = load_shares()
        shares = [s for s in shares if s.get('path') != path]
        file_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        is_dir = os.path.isdir(file_path)
        shares.insert(0, {'token': token, 'path': path, 'created_at': datetime.now().isoformat(), 'is_dir': is_dir})
        save_shares(shares)

    def remove_share(token):
        shares = load_shares()
        shares = [s for s in shares if s.get('token') != token]
        save_shares(shares)

    def get_file_info(path):
        if not os.path.exists(path):
            return None
        stat = os.stat(path)
        relative_path = os.path.relpath(path, UPLOAD_FOLDER).replace(os.sep, '/')
        is_dir = os.path.isdir(path)
        locked = False
        if is_dir:
            locks = load_locks()
            if relative_path in locks:
                full_lock_path = os.path.join(UPLOAD_FOLDER, relative_path.lstrip('/'))
                if os.path.exists(full_lock_path):
                    locked = True
        return {
            'name': os.path.basename(path),
            'path': relative_path,
            'full_path': path,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'is_dir': is_dir,
            'type': 'directory' if is_dir else 'file',
            'locked': locked
        }

    def list_directory(path):
        if not os.path.exists(path):
            return []
        items = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            items.append(get_file_info(item_path))
        return sorted(items, key=lambda x: (not x['is_dir'], x['name'].lower()))

    def is_authenticated():
        if request.authorization:
            username = request.authorization.username
            password = request.authorization.password
            config_data = load_config()
            if username == config_data.get('username', 'admin') and password == config_data.get('password', '123456'):
                return True
        return False

    def check_path_in_locked_dir(path):
        relative_path = os.path.relpath(path, UPLOAD_FOLDER).replace(os.sep, '/')
        parts = relative_path.split('/')
        for i in range(len(parts)):
            check_path = '/'.join(parts[:i+1]) if parts[:i+1] else ''
            if check_path and is_path_locked(check_path):
                return True
        return False

    def authenticate(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if request.authorization:
                username = request.authorization.username
                password = request.authorization.password
                config_data = load_config()
                if username == config_data.get('username', 'admin') and password == config_data.get('password', '123456'):
                    return f(*args, **kwargs)
            return jsonify({'error': 'Authentication required'}), 401, {'WWW-Authenticate': 'Basic realm="File Manager"'}
        return decorated

    app.add_url_rule('/img/<path:filename>', endpoint='img', view_func=lambda filename: send_from_directory(IMG_FOLDER, filename))

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/public-config')
    def public_config():
        config_data = load_config()
        return jsonify({
            'network_name': config_data.get('network_name', 'Local_Pan'),
            'network_logo': config_data.get('network_logo', ''),
            'copyright_year': config_data.get('copyright_year', ''),
            'copyright_domain': config_data.get('copyright_domain', ''),
            'server_start_time': time.time()
        })

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

            old_port = config_data.get('port')
            old_https_port = config_data.get('https_port')
            old_webdav_enabled = config_data.get('webdav_enabled')
            old_webdav_port = config_data.get('webdav_port')
            old_webdav_https_enabled = config_data.get('webdav_https_enabled')
            old_webdav_https_port = config_data.get('webdav_https_port')
            old_samba_enabled = config_data.get('samba_enabled')
            old_samba_port = config_data.get('samba_port')
            old_ftp_enabled = config_data.get('ftp_enabled')
            old_ftp_port = config_data.get('ftp_port')
            old_ssl_crt = config_data.get('ssl_crt', '')
            old_ssl_key = config_data.get('ssl_key', '')
            old_https_enabled = config_data.get('https_enabled', False)

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

            needs_restart = False
            services_to_restart = []

            if new_port is not None and new_port != old_port:
                needs_restart = True
                services_to_restart.append('http')
            if new_https_port is not None and new_https_port != old_https_port:
                needs_restart = True
                services_to_restart.append('https')
            if https_enabled != old_https_enabled:
                needs_restart = True
                if https_enabled:
                    services_to_restart.append('https')
                else:
                    services_to_restart.append('https')
            if webdav_enabled != old_webdav_enabled or (webdav_port is not None and webdav_port != old_webdav_port):
                needs_restart = True
                services_to_restart.append('webdav')
            if webdav_https_enabled != old_webdav_https_enabled or (webdav_https_port is not None and webdav_https_port != old_webdav_https_port):
                needs_restart = True
                services_to_restart.append('webdav_https')
            if samba_enabled != old_samba_enabled or (samba_port is not None and samba_port != old_samba_port):
                needs_restart = True
                services_to_restart.append('samba')
            if ftp_enabled != old_ftp_enabled or (ftp_port is not None and ftp_port != old_ftp_port):
                needs_restart = True
                services_to_restart.append('ftp')
            
            if ssl_crt != old_ssl_crt or ssl_key != old_ssl_key:
                if old_https_enabled or https_enabled:
                    needs_restart = True
                    services_to_restart.append('https')
                if old_webdav_https_enabled or webdav_https_enabled:
                    needs_restart = True
                    services_to_restart.append('webdav_https')
            
            services_to_restart = list(set(services_to_restart))

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

            https_available = bool(https_enabled and ssl_crt_path and ssl_key_path and os.path.exists(ssl_crt_path) and os.path.exists(ssl_key_path))

            if needs_restart:
                def restart_services():
                    import urllib.request
                    import urllib.error
                    import time
                    time.sleep(1)
                    for service in services_to_restart:
                        try:
                            req = urllib.request.Request('http://localhost:8088/api/restart-service', 
                                                        data=json.dumps({'service': service}).encode('utf-8'),
                                                        headers={'Content-Type': 'application/json'},
                                                        method='POST')
                            urllib.request.urlopen(req, timeout=5)
                        except Exception as e:
                            app.logger.error(f'Failed to restart {service} service: {e}')
                
                import threading
                thread = threading.Thread(target=restart_services)
                thread.daemon = True
                thread.start()

            return jsonify({
                'success': True,
                'needs_restart': needs_restart,
                'https_available': https_available,
                'https_will_be_enabled': https_enabled and https_available,
                'https_port': new_https_port if new_https_port is not None else config_data.get('https_port'),
                'services_restarted': services_to_restart
            })

    @app.route('/api/login')
    def api_login():
        auth = request.authorization
        config_data = load_config()
        if auth and auth.username == config_data.get('username', 'admin') and auth.password == config_data.get('password', '123456'):
            return jsonify({'success': True})
        return jsonify({'success': False}), 401

    @app.route('/api/files')
    def api_list_files():
        path = request.args.get('path', '')
        target_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not target_path.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        if not os.path.exists(target_path):
            return jsonify({'error': 'Path not found'}), 404
        if os.path.isfile(target_path):
            return jsonify(get_file_info(target_path))
        relative_path = os.path.relpath(target_path, UPLOAD_FOLDER).replace(os.sep, '/')
        if is_path_locked(relative_path if relative_path != '.' else '') and not is_authenticated():
            return jsonify({'error': 'Access denied'}), 403
        items = list_directory(target_path)
        if not is_authenticated():
            items = [item for item in items if not item.get('locked', False)]
        return jsonify({
            'items': items,
            'path': path,
            'parent': os.path.relpath(os.path.dirname(target_path), UPLOAD_FOLDER) if target_path != UPLOAD_FOLDER else None
        })

    @app.route('/api/search')
    def api_search():
        keyword = request.args.get('keyword', '').lower()
        if not keyword:
            return jsonify({'items': [], 'total': 0})
        results = []
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for name in files + dirs:
                if keyword in name.lower():
                    full_path = os.path.join(root, name)
                    item = get_file_info(full_path)
                    if item:
                        results.append(item)
        results.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        if not is_authenticated():
            results = [item for item in results if not item.get('locked', False)]
        return jsonify({'items': results, 'total': len(results)})

    def get_unique_filename(target_dir, filename):
        if not os.path.exists(os.path.join(target_dir, filename)):
            return filename
        name, ext = os.path.splitext(filename)
        counter = 1
        while True:
            new_filename = f"{name} ({counter}){ext}"
            if not os.path.exists(os.path.join(target_dir, new_filename)):
                return new_filename
            counter += 1

    @app.route('/api/upload', methods=['POST'])
    @authenticate
    def api_upload():
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        path = request.form.get('path', '')
        target_dir = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not target_dir.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        os.makedirs(target_dir, exist_ok=True)
        filename = get_unique_filename(target_dir, file.filename)
        file_path = os.path.join(target_dir, filename)
        file.save(file_path)
        return jsonify(get_file_info(file_path))

    @app.route('/api/download')
    def api_download():
        path = request.args.get('path', '')
        file_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not file_path.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        if os.path.isdir(file_path):
            return jsonify({'error': 'Cannot download directory'}), 400
        if check_path_in_locked_dir(file_path) and not is_authenticated():
            return jsonify({'error': 'Access denied'}), 403
        return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))

    @app.route('/api/share/<token>/<filename>')
    def api_share(token, filename):
        share = get_share_by_token(token)
        if not share:
            return jsonify({'error': 'Share link not found or expired'}), 404
        path = share.get('path', '')
        file_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not file_path.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        if os.path.isdir(file_path):
            return jsonify({'error': 'Cannot share directory'}), 400
        return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))

    @app.route('/api/shares', methods=['GET'])
    def api_get_shares():
        shares = load_shares()
        for share in shares:
            path = share.get('path', '')
            file_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
            share['is_dir'] = os.path.isdir(file_path)
        return jsonify(shares)

    @app.route('/api/shares', methods=['POST'])
    @authenticate
    def api_add_share():
        data = request.get_json()
        token = data.get('token', '')
        path = data.get('path', '')
        if not token or not path:
            return jsonify({'error': 'Token and path required'}), 400
        add_or_update_share(token, path)
        return jsonify({'success': True})

    @app.route('/api/shares/<token>', methods=['DELETE'])
    @authenticate
    def api_delete_share(token):
        remove_share(token)
        return jsonify({'success': True})

    @app.route('/api/shares', methods=['DELETE'])
    @authenticate
    def api_delete_shares():
        data = request.get_json()
        tokens = data.get('tokens', [])
        for token in tokens:
            remove_share(token)
        return jsonify({'success': True})

    @app.route('/api/mkdir', methods=['POST'])
    @authenticate
    def api_mkdir():
        data = request.get_json()
        path = data.get('path', '')
        name = data.get('name', '')
        if not name:
            return jsonify({'error': 'Directory name required'}), 400
        target_dir = os.path.join(UPLOAD_FOLDER, path.lstrip('/'), name)
        if not target_dir.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        os.makedirs(target_dir, exist_ok=True)
        return jsonify(get_file_info(target_dir))

    @app.route('/api/mkdirs', methods=['POST'])
    @authenticate
    def api_mkdirs():
        data = request.get_json()
        path = data.get('path', '')
        if not path:
            return jsonify({'error': 'Path required'}), 400
        target_dir = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not target_dir.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        os.makedirs(target_dir, exist_ok=True)
        return jsonify({'success': True, 'path': path})

    @app.route('/api/delete', methods=['DELETE'])
    @authenticate
    def api_delete():
        path = request.args.get('path', '')
        file_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not file_path.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        if os.path.isdir(file_path):
            import shutil
            shutil.rmtree(file_path)
            cleanup_invalid_locks()
        else:
            os.remove(file_path)
        return jsonify({'success': True})

    @app.route('/api/lock', methods=['POST'])
    @authenticate
    def api_lock():
        data = request.get_json()
        path = data.get('path', '')
        file_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not file_path.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        if not os.path.exists(file_path):
            return jsonify({'error': 'Path not found'}), 404
        if not os.path.isdir(file_path):
            return jsonify({'error': 'Only directories can be locked'}), 400
        relative_path = os.path.relpath(file_path, UPLOAD_FOLDER).replace(os.sep, '/')
        set_path_locked(relative_path, True)
        return jsonify({'success': True, 'locked': True})

    @app.route('/api/unlock', methods=['POST'])
    @authenticate
    def api_unlock():
        data = request.get_json()
        path = data.get('path', '')
        file_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not file_path.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        relative_path = os.path.relpath(file_path, UPLOAD_FOLDER).replace(os.sep, '/')
        set_path_locked(relative_path, False)
        return jsonify({'success': True, 'locked': False})

    @app.route('/api/rename', methods=['POST'])
    @authenticate
    def api_rename():
        data = request.get_json()
        path = data.get('path', '')
        new_name = data.get('new_name', '')
        if not new_name:
            return jsonify({'error': 'New name required'}), 400
        old_path = os.path.join(UPLOAD_FOLDER, path.lstrip('/'))
        if not old_path.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        if not os.path.exists(old_path):
            return jsonify({'error': 'File not found'}), 404
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        if not new_path.startswith(UPLOAD_FOLDER):
            return jsonify({'error': 'Invalid path'}), 400
        is_dir = os.path.isdir(old_path)
        if is_dir:
            old_relative_path = os.path.relpath(old_path, UPLOAD_FOLDER).replace(os.sep, '/')
            was_locked = is_path_locked(old_relative_path)
        os.rename(old_path, new_path)
        if is_dir and was_locked:
            new_relative_path = os.path.relpath(new_path, UPLOAD_FOLDER).replace(os.sep, '/')
            set_path_locked(new_relative_path, True)
        return jsonify(get_file_info(new_path))

    @app.route('/api/cleanup-hidden', methods=['POST'])
    @authenticate
    def api_cleanup_hidden():
        deleted_count = 0
        errors = []
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for name in files + dirs:
                if name.startswith('.'):
                    item_path = os.path.join(root, name)
                    try:
                        if os.path.isdir(item_path):
                            import shutil
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                        deleted_count += 1
                    except Exception as e:
                        errors.append(f'{name}: {str(e)}')
        return jsonify({'success': True, 'deleted_count': deleted_count, 'errors': errors})

    @app.route('/webdav/', methods=['PROPFIND', 'OPTIONS'])
    @app.route('/webdav/<path:path>', methods=['PROPFIND', 'OPTIONS', 'GET', 'PUT', 'DELETE', 'MKCOL', 'MOVE'])
    @authenticate
    def webdav(path=''):
        if request.method == 'OPTIONS':
            return '', 200, {
                'Allow': 'OPTIONS, PROPFIND, GET, PUT, DELETE, MKCOL, MOVE',
                'DAV': '1',
                'MS-Author-Via': 'DAV'
            }
        dav_path = '/' + path
        file_path = os.path.join(UPLOAD_FOLDER, dav_path.lstrip('/'))
        if not file_path.startswith(UPLOAD_FOLDER):
            return '403 Forbidden', 403
        if request.method == 'PROPFIND':
            if not os.path.exists(file_path):
                return '404 Not Found', 404
            xml = ['<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:">']
            stat = os.stat(file_path)
            is_dir = os.path.isdir(file_path)
            size = stat.st_size if not is_dir else 0
            modified = datetime.fromtimestamp(stat.st_mtime).strftime('%a, %d %b %Y %H:%M:%S GMT')
            resource_type = '<d:collection/>' if is_dir else ''
            display_name = os.path.basename(file_path)
            xml.append(f'<d:response><d:href>/{display_name}</d:href><d:propstat><d:prop><d:displayname>{display_name}</d:displayname><d:getcontentlength>{size}</d:getcontentlength><d:getlastmodified>{modified}</d:getlastmodified><d:resourcetype>{resource_type}</d:resourcetype></d:prop></d:propstat></d:response>')
            if is_dir:
                for item in os.listdir(file_path):
                    item_path = os.path.join(file_path, item)
                    item_stat = os.stat(item_path)
                    item_is_dir = os.path.isdir(item_path)
                    item_size = item_stat.st_size if not item_is_dir else 0
                    item_modified = datetime.fromtimestamp(item_stat.st_mtime).strftime('%a, %d %b %Y %H:%M:%S GMT')
                    item_resource_type = '<d:collection/>' if item_is_dir else ''
                    xml.append(f'<d:response><d:href>/{item}</d:href><d:propstat><d:prop><d:displayname>{item}</d:displayname><d:getcontentlength>{item_size}</d:getcontentlength><d:getlastmodified>{item_modified}</d:getlastmodified><d:resourcetype>{item_resource_type}</d:resourcetype></d:prop></d:propstat></d:response>')
            xml.append('</d:multistatus>')
            return ''.join(xml), 207, {'Content-Type': 'application/xml'}
        if request.method == 'GET':
            if not os.path.exists(file_path) or os.path.isdir(file_path):
                return '404 Not Found', 404
            return send_file(file_path)
        if request.method == 'PUT':
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(request.data)
            return '201 Created', 201
        if request.method == 'DELETE':
            if not os.path.exists(file_path):
                return '404 Not Found', 404
            if os.path.isdir(file_path):
                import shutil
                shutil.rmtree(file_path)
                cleanup_invalid_locks()
            else:
                os.remove(file_path)
            return '204 No Content', 204
        if request.method == 'MKCOL':
            if os.path.exists(file_path):
                return '405 Method Not Allowed', 405
            os.makedirs(file_path)
            return '201 Created', 201
        if request.method == 'MOVE':
            dest = request.headers.get('Destination', '')
            if not dest:
                return '400 Bad Request', 400
            dest_path = os.path.join(UPLOAD_FOLDER, dest.replace('http://localhost:8081/webdav', '').lstrip('/'))
            if not dest_path.startswith(UPLOAD_FOLDER):
                return '403 Forbidden', 403
            os.rename(file_path, dest_path)
            return '201 Created', 201
        return '405 Method Not Allowed', 405

    return app

def run_http_server(port=8080):
    config = get_config()
    port = config.get('port', 8080)
    app = create_flask_app()

    logger.info(f'HTTP File Manager running on http://0.0.0.0:{port}/')

    try:
        run_simple('0.0.0.0', port, app, use_reloader=False, use_debugger=False, threaded=True)
    except Exception as e:
        logger.error(f'HTTP server failed: {str(e)}')
        return 1
    return 0

def run_https_server():
    config = get_config()
    port = config.get('https_port', '')
    ssl_crt = config.get('ssl_crt', '')
    ssl_key = config.get('ssl_key', '')

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ssl_crt_path = os.path.join(base_dir, ssl_crt) if ssl_crt else ''
    ssl_key_path = os.path.join(base_dir, ssl_key) if ssl_key else ''

    if not ssl_crt_path or not ssl_key_path or not os.path.exists(ssl_crt_path) or not os.path.exists(ssl_key_path):
        logger.error('SSL certificate or key not configured properly')
        return 1

    app = create_flask_app()

    logger.info(f'HTTPS File Manager running on https://0.0.0.0:{port}/')

    try:
        run_simple('0.0.0.0', port, app, use_reloader=False, use_debugger=False, threaded=True, ssl_context=(ssl_crt_path, ssl_key_path))
    except Exception as e:
        logger.error(f'HTTPS server failed: {str(e)}')
        return 1
    return 0

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Web Server for Local_Pan')
    parser.add_argument('--mode', choices=['http', 'https'], default='http', help='Server mode')
    args = parser.parse_args()
    
    if args.mode == 'https':
        sys.exit(run_https_server())
    else:
        sys.exit(run_http_server())