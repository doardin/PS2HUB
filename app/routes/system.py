from flask import Blueprint, current_app, jsonify, request
import psutil
import subprocess
import os
import signal
system_bp = Blueprint('system', __name__)

def is_process_running(process_name):
    """Check if there is any running process that contains the given name."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if process_name in proc.info['name'] or \
               (proc.info['cmdline'] and any(process_name in cmd for cmd in proc.info['cmdline'])):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False



@system_bp.route('/stats')
def system_stats():
    # CPU
    cpu_percent = psutil.cpu_percent(interval=None) # Non-blocking

    # RAM
    mem = psutil.virtual_memory()
    ram_percent = mem.percent
    ram_used = mem.used
    ram_total = mem.total

    # Disk (Using PS2_ROOT or root)
    disk_path = os.environ.get('PS2_ROOT', '/')
    try:
        disk = psutil.disk_usage(disk_path)
        disk_percent = disk.percent
        disk_used = disk.used
        disk_total = disk.total
    except OSError:
        disk_percent = 0
        disk_used = 0
        disk_total = 0

    services = {
        'aria2c': is_process_running('aria2c')
    }

    return jsonify({
        'cpu': {
            'percent': cpu_percent
        },
        'ram': {
            'percent': ram_percent,
            'used': ram_used,
            'total': ram_total
        },
        'disk': {
            'percent': disk_percent,
            'used': disk_used,
            'total': disk_total
        },
        'services': services
    })


@system_bp.route('/services/aria2c', methods=['POST'])
def control_aria2c():
    """Start or stop the aria2c service."""
    data = request.get_json(silent=True) or {}
    action = data.get('action', '').strip().lower()

    if action not in ('start', 'stop'):
        return jsonify({'error': 'Ação inválida. Use "start" ou "stop".'}), 400

    if action == 'start':
        if is_process_running('aria2c'):
            return jsonify({'message': 'aria2c já está rodando', 'running': True})

        secret = current_app.config.get('ARIA2_RPC_SECRET', 'ps2hub')
        download_dir = current_app.config.get('DOWNLOADS_DIR', '/tmp')
        os.makedirs(download_dir, exist_ok=True)

        try:
            subprocess.Popen([
                'aria2c',
                '--enable-rpc',
                '--rpc-listen-all=false',
                '--rpc-listen-port=6800',
                f'--rpc-secret={secret}',
                f'--dir={download_dir}',
                '--file-allocation=none',
                '--daemon=true',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            return jsonify({'message': 'aria2c iniciado com sucesso', 'running': True})
        except FileNotFoundError:
            return jsonify({
                'error': 'aria2c não encontrado. Instale com: sudo apt install aria2'
            }), 500
        except Exception as e:
            return jsonify({'error': f'Erro ao iniciar aria2c: {e}'}), 500

    else:  # stop
        if not is_process_running('aria2c'):
            return jsonify({'message': 'aria2c já está parado', 'running': False})

        killed = False
        for proc in psutil.process_iter(['name', 'cmdline', 'pid']):
            try:
                if 'aria2c' in proc.info['name'] or \
                   (proc.info['cmdline'] and any('aria2c' in cmd for cmd in proc.info['cmdline'])):
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if killed:
            return jsonify({'message': 'aria2c parado com sucesso', 'running': False})
        else:
            return jsonify({'error': 'Não foi possível parar o aria2c'}), 500


