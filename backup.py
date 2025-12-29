import os
import shutil
import zipfile
import glob
from datetime import datetime
import logging

# Get the directory where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DB_FILE = os.path.join(BASE_DIR, "trades.db")
ENV_FILE = os.path.join(BASE_DIR, ".env")

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def create_backup():
    """Creates a zip backup of trades.db and .env"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.zip"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        with zipfile.ZipFile(backup_path, 'w') as zipf:
            if os.path.exists(DB_FILE):
                zipf.write(DB_FILE, arcname="trades.db")
            if os.path.exists(ENV_FILE):
                zipf.write(ENV_FILE, arcname=".env")
                
        # Clean up old backups (keep last 10)
        cleanup_backups()
        
        return {
            "status": "success", 
            "filename": backup_filename, 
            "timestamp": timestamp,
            "path": os.path.abspath(backup_path)
        }
    except Exception as e:
        logging.error(f"Backup failed: {e}")
        return {"status": "error", "message": str(e)}

def list_backups():
    """Lists available backups"""
    files = glob.glob(os.path.join(BACKUP_DIR, "*.zip"))
    backups = []
    
    for f in files:
        stats = os.stat(f)
        backups.append({
            "filename": os.path.basename(f),
            "size": stats.st_size,
            "created": datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        })
        
    # Sort by created desc
    backups.sort(key=lambda x: x['filename'], reverse=True)
    return backups

def restore_backup(filename):
    """Restores trades.db from a specific backup zip"""
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        return {"status": "error", "message": "Backup file not found"}
        
    try:
        # Create a temp backup of current state just in case
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.exists(DB_FILE):
             shutil.copy2(DB_FILE, f"{DB_FILE}.pre_restore_{timestamp}.bak")
             
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extract("trades.db", path=BASE_DIR)
            # We typically don't restore .env automatically to avoid breaking config
            
        return {"status": "success", "message": f"Restored from {filename}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def cleanup_backups(keep=10):
    """Deletes old backups, keeping only the last N"""
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, "*.zip")), reverse=True)
    if len(files) > keep:
        for f in files[keep:]:
            try:
                os.remove(f)
                logging.info(f"Deleted old backup: {f}")
            except Exception as e:
                logging.error(f"Error deleting {f}: {e}")
