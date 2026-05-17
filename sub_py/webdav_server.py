import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import get_config, UPLOAD_FOLDER

def setup_logger():
    logger = logging.getLogger('webdav_server')
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

class WebDAVLoggingMiddleware:
    def __init__(self, app):
        self.app = app
    
    def _get_webdav_operation(self, method, path):
        if method == 'PROPFIND':
            return {'type': 'WebDAV浏览', 'target': path}
        elif method == 'GET':
            return {'type': 'WebDAV下载', 'target': path}
        elif method == 'PUT':
            return {'type': 'WebDAV上传', 'target': path}
        elif method == 'DELETE':
            return {'type': 'WebDAV删除', 'target': path}
        elif method == 'MKCOL':
            return {'type': 'WebDAV创建目录', 'target': path}
        elif method == 'MOVE':
            return {'type': 'WebDAV移动', 'target': path}
        elif method == 'OPTIONS':
            return None
        else:
            return {'type': f'WebDAV {method}', 'target': path}
    
    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', '')
        path = environ.get('PATH_INFO', '')
        remote_addr = environ.get('REMOTE_ADDR', '')
        
        details = self._get_webdav_operation(method, path)
        if details:
            logger.info(f"[请求] IP:{remote_addr} | 操作:{details['type']} | 对象:{details['target']}")
        
        def log_start_response(status, headers, exc_info=None):
            if details:
                logger.info(f"[响应] IP:{remote_addr} | 操作:{details['type']} | 对象:{details['target']} | 状态:{status}")
            return start_response(status, headers, exc_info)
        
        return self.app(environ, log_start_response)

def run_webdav_server(use_ssl=False):
    from wsgidav.wsgidav_app import WsgiDAVApp
    from cheroot import wsgi
    from cheroot.ssl.builtin import BuiltinSSLAdapter
    
    config = get_config()
    
    if use_ssl:
        port = config.get('webdav_https_port', 5002)
        ssl_crt = config.get('ssl_crt', '')
        ssl_key = config.get('ssl_key', '')
        ssl_crt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ssl_crt) if ssl_crt else ''
        ssl_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ssl_key) if ssl_key else ''
    else:
        port = config.get('webdav_port', 5001)
        ssl_crt_path = None
        ssl_key_path = None
    
    app = WsgiDAVApp({
        'provider_mapping': {
            '/': UPLOAD_FOLDER
        },
        'simple_dc': {
            'user_mapping': {
                '/': {
                    config['username']: {
                        'password': config['password']
                    }
                }
            }
        },
        'host': '0.0.0.0',
        'port': port,
        'authenticator': 'httpd_wsgidav_authenticator.WsgiDAVAuthenticator',
        'middleware_args': {
            'domain_controller': None
        }
    })
    
    app = WebDAVLoggingMiddleware(app)
    server = wsgi.Server(('0.0.0.0', port), app)
    
    protocol = 'https' if use_ssl else 'http'
    
    if use_ssl and ssl_crt_path and ssl_key_path:
        try:
            server.ssl_adapter = BuiltinSSLAdapter(ssl_crt_path, ssl_key_path)
            logger.info(f'WebDAV HTTPS setup with cert: {ssl_crt_path}')
        except Exception as e:
            logger.error(f'WebDAV HTTPS setup failed: {str(e)}')
            print(f'WebDAV HTTPS setup failed: {str(e)}')
            return 1
    
    print(f'WebDAV server running on {protocol}://0.0.0.0:{port}/webdav/')
    logger.info(f'WebDAV server started on {protocol}://0.0.0.0:{port}/webdav/')
    
    try:
        server.start()
    except Exception as e:
        logger.error(f'WebDAV server failed: {str(e)}')
        print(f'WebDAV server error: {str(e)}')
        return 1
    return 0

if __name__ == '__main__':
    use_ssl = len(sys.argv) > 1 and sys.argv[1] == '--ssl'
    sys.exit(run_webdav_server(use_ssl))
