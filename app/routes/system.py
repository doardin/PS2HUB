from flask import Blueprint, jsonify, request
import psutil
import subprocess
import os

system_bp = Blueprint('system', __name__)

# Map service names to their systemd unit / process info
SERVICE_MAP = {
    'smbd': {
        'systemd': 'smbd',
        'label': 'Samba',
    },
    'aria2c': {
        'systemd': 'ps2hub-aria2',
        'label': 'aria2c',
    },
}

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

    # Services
    services = {
        'aria2c': is_process_running('aria2c'),
        'smbd': is_process_running('smbd')
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


@system_bp.route('/service/<service_name>/<action>', methods=['POST'])
def service_control(service_name, action):
    """Control a service: start, stop, or restart."""
    if service_name not in SERVICE_MAP:
        return jsonify({'ok': False, 'error': f'Serviço desconhecido: {service_name}'}), 400

    if action not in ('start', 'stop', 'restart'):
        return jsonify({'ok': False, 'error': f'Ação inválida: {action}'}), 400

    unit = SERVICE_MAP[service_name]['systemd']

    try:
        result = subprocess.run(
            ['sudo', 'systemctl', action, unit],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return jsonify({'ok': True, 'message': f'{SERVICE_MAP[service_name]["label"]} {action} executado.'})
        else:
            return jsonify({'ok': False, 'error': result.stderr.strip() or 'Falha ao executar comando.'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'error': 'Timeout ao executar comando.'}), 504
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

