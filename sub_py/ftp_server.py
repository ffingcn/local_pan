import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import get_config, UPLOAD_FOLDER

def setup_logger():
    logger = logging.getLogger('ftp_server')
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

def run_ftp_server():
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    
    config = get_config()
    
    port = config.get('ftp_port', 21)
    passive_min = config.get('ftp_passive_min')
    passive_max = config.get('ftp_passive_max')
    username = config.get('username')
    password = config.get('password')
    
    ftp_authorizer = DummyAuthorizer()
    ftp_authorizer.add_user(username, password, UPLOAD_FOLDER, perm='elradfmw')
    
    handler = FTPHandler
    handler.authorizer = ftp_authorizer
    handler.passive_ports = range(passive_min, passive_max + 1)
    handler.banner = "Local_Pan FTP Server ready."
    
    server = FTPServer(('0.0.0.0', port), handler)
    server.max_cons = 256
    server.max_cons_per_ip = 5
    
    print(f'FTP server running on ftp://0.0.0.0:{port}/')
    print(f'FTP login: username={username}, password={password}')
    logger.info(f'FTP server started on ftp://0.0.0.0:{port}/')
    
    try:
        server.serve_forever()
    except Exception as e:
        logger.error(f'FTP server failed: {str(e)}')
        print(f'FTP server error: {str(e)}')
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(run_ftp_server())
