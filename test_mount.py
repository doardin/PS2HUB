import os
import stat
from app import create_app

app = create_app()
with app.app_context():
    temp_dir = os.path.join(app.config['DOWNLOADS_DIR'], 'temp_uploads')
    dvd_dir = app.config['DVD_DIR']
    
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(dvd_dir, exist_ok=True)
    
    st1 = os.stat(temp_dir)
    st2 = os.stat(dvd_dir)
    
    print(f"temp_dir dev: {st1.st_dev}")
    print(f"dvd_dir dev: {st2.st_dev}")
    print("Same filesystem?", st1.st_dev == st2.st_dev)
