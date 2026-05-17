#!/usr/bin/env python3
import os
import sys
import subprocess
import signal
import json

def get_config_ports():
    """从config.json读取配置的端口"""
    ports = [8088]  # 管理API默认端口
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'config.json')
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # 添加配置中的端口
            if 'port' in config:
                ports.append(config['port'])
            if 'https_port' in config:
                ports.append(config['https_port'])
            if 'webdav_port' in config:
                ports.append(config['webdav_port'])
            if 'webdav_https_port' in config:
                ports.append(config['webdav_https_port'])
            if 'ftp_port' in config:
                ports.append(config['ftp_port'])
            if 'samba_port' in config:
                ports.append(config['samba_port'])
        except Exception as e:
            print(f'读取配置文件失败，使用默认端口: {e}')
    
    return list(set(ports))

def get_pids_by_name(process_name):
    """通过进程名获取PID列表"""
    pids = []
    try:
        if sys.platform == 'darwin' or sys.platform == 'linux':
            # macOS 和 Linux 使用 ps 命令，不限制特定的python路径
            result = subprocess.run(
                ['ps', '-ef'],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                # 匹配包含python且包含目标进程名的行
                if (('python' in line.lower() or 'python3' in line.lower()) and process_name in line):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            pids.append(int(parts[1]))
                        except:
                            pass
        elif sys.platform == 'win32':
            # Windows 使用 tasklist 命令
            result = subprocess.run(
                ['tasklist', '/FI', f'IMAGENAME eq python.exe', '/FO', 'CSV'],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            for line in result.stdout.split('\n'):
                if process_name in line:
                    try:
                        pid = int(line.split(',')[1].strip('"'))
                        pids.append(pid)
                    except:
                        pass
    except Exception as e:
        print(f'获取进程列表时出错: {e}')
    
    return pids

def get_pids_by_port(port):
    """通过端口号获取PID列表"""
    pids = []
    try:
        if sys.platform == 'darwin' or sys.platform == 'linux':
            # macOS 和 Linux 使用 lsof 命令
            result = subprocess.run(
                ['lsof', '-i', f':{port}', '-t'],
                capture_output=True,
                text=True
            )
            for pid_str in result.stdout.strip().split('\n'):
                if pid_str.strip():
                    try:
                        pids.append(int(pid_str.strip()))
                    except:
                        pass
        elif sys.platform == 'win32':
            # Windows 使用 netstat 命令
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'tcp'],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            for line in result.stdout.split('\n'):
                if f':{port}' in line:
                    parts = line.split()
                    if parts:
                        try:
                            pid = int(parts[-1])
                            pids.append(pid)
                        except:
                            pass
    except Exception as e:
        pass
    
    return pids

def get_all_related_pids():
    """获取所有相关进程的PID"""
    pids = set()
    
    # 方式1：通过进程名查找
    process_names = ['app.py', 'web_server.py', 'ftp_server.py', 'webdav_server.py', 'samba_server.py']
    for name in process_names:
        pids.update(get_pids_by_name(name))
    
    # 方式2：通过端口号查找（从配置文件读取）
    ports = get_config_ports()
    print(f'检测端口: {ports}')
    for port in ports:
        pids.update(get_pids_by_port(port))
    
    # 排除当前脚本自身的PID
    current_pid = os.getpid()
    pids.discard(current_pid)
    
    return list(pids)

def stop_pid(pid):
    """停止指定PID的进程"""
    try:
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], check=True, capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            # 等待进程结束
            try:
                os.waitpid(pid, 0)
            except:
                pass
        return True
    except Exception as e:
        # 如果优雅停止失败，尝试强制杀死
        try:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/PID', str(pid)], check=True, capture_output=True)
            else:
                os.kill(pid, signal.SIGKILL)
            return True
        except:
            return False

def stop_processes(pids):
    """停止所有进程"""
    if not pids:
        print('没有找到相关进程')
        return False
    
    print(f'找到 {len(pids)} 个相关进程:')
    for pid in pids:
        print(f'  PID {pid}')
    
    print('\n正在停止进程...')
    stopped_count = 0
    
    for pid in pids:
        if stop_pid(pid):
            stopped_count += 1
            print(f'  PID {pid} 已停止')
        else:
            print(f'  PID {pid} 停止失败')
    
    print(f'\n已停止 {stopped_count} 个进程')
    return True

def main():
    print('=' * 50)
    print('Local_Pan 应用停止脚本')
    print('=' * 50)
    
    pids = get_all_related_pids()
    
    if not pids:
        print('没有运行中的应用进程')
        sys.exit(0)
    
    stop_processes(pids)
    
    print('\n应用已停止！')

if __name__ == '__main__':
    main()
