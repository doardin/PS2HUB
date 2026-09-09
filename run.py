#!/usr/bin/env python3
"""PS2 Hub — Development server entry point."""
import os
from app import create_app

# For development, use a local data directory instead of /srv/ps2
if not os.environ.get('PS2_ROOT'):
    dev_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.environ['PS2_ROOT'] = dev_root

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
