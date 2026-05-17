import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import get_config, UPLOAD_FOLDER

def setup_logger():
    logger = logging.getLogger('samba_server')
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

def run_samba_server():
    try:
        from impacket.smbserver import SimpleSMBServer
        from impacket.ntlm import compute_lmhash, compute_nthash
    except ImportError as e:
        logger.error(f'Impacket library not found or incompatible version: {str(e)}')
        print(f'Error: Impacket library not found or incompatible version: {str(e)}')
        return 1
    
    config = get_config()
    
    port = config.get('samba_port', 445)
    username = config.get('username', 'admin')
    password = config.get('password', '123456')
    network_name = config.get('network_name', 'Local_Pan')
    
    try:
        server = SimpleSMBServer()
        server.setSMB2Support(True)
        server.addShare(network_name, UPLOAD_FOLDER, 'Local Pan File Share', '0', 'no')
        
        lmhash = compute_lmhash(password)
        nthash = compute_nthash(password)
        server.addCredential(username, 0, lmhash, nthash)
        
        print(f'Samba server running on smb://0.0.0.0:{port}/')
        print(f'Samba login: username={username}, password={password}')
        logger.info(f'Samba server started on smb://0.0.0.0:{port}/')
        
        server.start()
        return 0
    except Exception as e:
        logger.error(f'Samba server failed: {str(e)}')
        print(f'Samba server error: {str(e)}')
        return 1

if __name__ == '__main__':
    sys.exit(run_samba_server())
