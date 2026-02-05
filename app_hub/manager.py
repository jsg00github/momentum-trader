
import os
import psutil
import subprocess
import shutil
import datetime
import threading
import time
import sys
import webbrowser

# Constants
BACKUP_DIR = os.path.join(os.getcwd(), "Historial_Backups")
APPS_CONFIG = [
    {
        "name": "Momentum Backend",
        "path": "backend/main.py",
        "type": "python",
        "cwd": ".", 
        "icon": "⚡",
        "url": "http://127.0.0.1:8000"
    },
    {
        "name": "Qulla-Catalyst Scanner",
        "path": "qulla_scanner/app.py",
        "type": "streamlit",
        "cwd": ".",
        "icon": "🚀",
        "url": "http://localhost:8501"
    }
]

class AppManager:
    def __init__(self):
        self.processes = {} # map app_name -> psutil.Process
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
            
    def scan_running_apps(self):
        """
        Tries to re-attach to running processes by checking cmdline.
        This is a best-effort heuristic.
        """
        for app in APPS_CONFIG:
            if app['name'] in self.processes and self.processes[app['name']].is_running():
                continue # Already tracking
            
            # Logic to find if app is already running externally?
            # Complex to do reliably without PID file. 
            # For this MVP, we largely track what WE started, but we could look for signatures.
            pass

    def start_app(self, app_name):
        app = next((a for a in APPS_CONFIG if a['name'] == app_name), None)
        if not app: return False, "Unknown App"
        
        if app_name in self.processes and self.processes[app_name].is_running():
            # If already running, maybe just open browser?
            if app.get('url'):
                webbrowser.open(app['url'])
                return True, "Opened Browser (App was running)"
            return False, "Already Running"
            
        try:
            cmd = []
            if app['type'] == 'python':
                cmd = [sys.executable, app['path']]
            elif app['type'] == 'streamlit':
                cmd = [sys.executable, "-m", "streamlit", "run", app['path']]
                
            # Launch
            p = subprocess.Popen(
                cmd, 
                cwd=os.path.abspath(app['cwd']),
                creationflags=subprocess.CREATE_NEW_CONSOLE # Open in new window
            )
            
            # Track
            self.processes[app_name] = psutil.Process(p.pid)
            
            # Open Browser after delay
            if app.get('url'):
                def open_browser():
                    time.sleep(3) # Wait for server to boot
                    webbrowser.open(app['url'])
                
                threading.Thread(target=open_browser, daemon=True).start()
            
            return True, "Started & Browser Opening..."
        except Exception as e:
            return False, str(e)

    def stop_app(self, app_name):
        if app_name in self.processes:
            proc = self.processes[app_name]
            try:
                # Kill children (important for shell=True or wrapper scripts)
                children = proc.children(recursive=True)
                for child in children:
                    child.kill()
                proc.kill()
                del self.processes[app_name]
                return True, "Stopped"
            except psutil.NoSuchProcess:
                del self.processes[app_name]
                return True, "Already Gone"
            except Exception as e:
                return False, str(e)
        return False, "Not Running"

    def restart_app(self, app_name):
        self.stop_app(app_name)
        time.sleep(1)
        return self.start_app(app_name)

    def kill_all(self):
        results = {}
        for name in list(self.processes.keys()):
            success, msg = self.stop_app(name)
            results[name] = success
        return results

    def get_stats(self):
        """
        Returns dict: {app_name: {'cpu': 0.0, 'ram_mb': 0.0, 'status': 'Running'}}
        """
        stats = {}
        for app in APPS_CONFIG:
            name = app['name']
            if name in self.processes:
                proc = self.processes[name]
                try:
                    if proc.is_running():
                        with proc.oneshot():
                            mem_info = proc.memory_info()
                            cpu_pct = proc.cpu_percent()
                            # Convert to MB
                            ram_mb = mem_info.rss / (1024 * 1024)
                            
                            stats[name] = {
                                'status': 'Running',
                                'cpu': cpu_pct,
                                'ram_mb': ram_mb
                            }
                    else:
                        del self.processes[name]
                        stats[name] = {'status': 'Stopped', 'cpu': 0, 'ram_mb': 0}
                except psutil.NoSuchProcess:
                    del self.processes[name]
                    stats[name] = {'status': 'Stopped', 'cpu': 0, 'ram_mb': 0}
            else:
                 stats[name] = {'status': 'Stopped', 'cpu': 0, 'ram_mb': 0}
        return stats

    def backup_app(self, app_name):
        app = next((a for a in APPS_CONFIG if a['name'] == app_name), None)
        if not app: return False, "Unknown App"
        
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            zip_name = f"{app_name.replace(' ', '_')}_{timestamp}"
            
            # Determine folder to zip (parent of the script usually)
            # app['path'] is relative e.g. "backend/main.py" -> zip "backend"
            target_dir = os.path.dirname(app['path'])
            if target_dir == "": target_dir = "." # unsafe to zip root
            
            if target_dir == ".":
                # Special case: don't zip the whole root, that's too big.
                # Maybe just zip specific tracked folders? 
                # For this MVP, let's assume valid structure.
                # Qulla uses qulla_scanner/, Backend uses backend/
                return False, "Cannot backup root"
            
            shutil.make_archive(
                os.path.join(BACKUP_DIR, zip_name), 
                'zip', 
                target_dir
            )
            return True, f"Backup saved: {zip_name}.zip"
        except Exception as e:
            return False, str(e)
