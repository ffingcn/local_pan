import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'config.json')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

DEFAULT_CONFIG = {
    'port': 8080,
    'https_port': 8443,
    'https_enabled': False,
    'webdav_enabled': True,
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
    'ftp_passive_min': 51000,
    'ftp_passive_max': 52000
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                config = {}
                for key in DEFAULT_CONFIG:
                    config[key] = data.get(key, DEFAULT_CONFIG[key])
                return config
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def get_config():
    return load_config()
