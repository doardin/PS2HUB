from flask import Blueprint, jsonify, request
import psutil
import subprocess
import os
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



