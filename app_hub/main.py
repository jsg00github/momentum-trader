
import customtkinter as ctk
import threading
import time
from manager import AppManager, APPS_CONFIG

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class AppCard(ctk.CTkFrame):
    def __init__(self, master, app_name, icon, manager):
        super().__init__(master)
        self.app_name = app_name
        self.manager = manager
        
        # Grid Setup
        self.grid_columnconfigure(1, weight=1)
        
        # Icon & Title
        self.lbl_icon = ctk.CTkLabel(self, text=icon, font=("Arial", 32))
        self.lbl_icon.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        
        self.lbl_title = ctk.CTkLabel(self, text=app_name, font=("Roboto Medium", 16))
        self.lbl_title.grid(row=0, column=1, sticky="w", padx=5, pady=(10,0))
        
        self.lbl_status = ctk.CTkLabel(self, text="Stopped", text_color="grey")
        self.lbl_status.grid(row=1, column=1, sticky="w", padx=5)
        
        # Stats
        self.lbl_ram = ctk.CTkLabel(self, text="RAM: 0 MB", font=("Roboto", 12))
        self.lbl_ram.grid(row=0, column=2, padx=10)
        
        self.lbl_cpu = ctk.CTkLabel(self, text="CPU: 0%", font=("Roboto", 12))
        self.lbl_cpu.grid(row=1, column=2, padx=10)
        
        # Buttons Frame
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        
        self.btn_run = ctk.CTkButton(self.btn_frame, text="▶ START", command=self.on_start, width=80, fg_color="green", hover_color="darkgreen")
        self.btn_run.pack(side="left", padx=5)
        
        self.btn_stop = ctk.CTkButton(self.btn_frame, text="⏹ STOP", command=self.on_stop, width=80, fg_color="red", hover_color="darkred", state="disabled")
        self.btn_stop.pack(side="left", padx=5)
        
        self.btn_restart = ctk.CTkButton(self.btn_frame, text="↺ RESET", command=self.on_restart, width=80, fg_color="orange", hover_color="darkorange", state="disabled")
        self.btn_restart.pack(side="left", padx=5)
        
        self.btn_backup = ctk.CTkButton(self.btn_frame, text="💾 BACKUP", command=self.on_backup, width=80)
        self.btn_backup.pack(side="right", padx=5)

    def on_start(self):
        success, msg = self.manager.start_app(self.app_name)
        if not success: print(msg) # Could add toast

    def on_stop(self):
        self.manager.stop_app(self.app_name)

    def on_restart(self):
        self.manager.restart_app(self.app_name)

    def on_backup(self):
        success, msg = self.manager.backup_app(self.app_name)
        print(msg) # Todo: visual feedback

    def update_state(self, stats):
        # Update Labels
        status = stats.get('status', 'Stopped')
        cpu = stats.get('cpu', 0)
        ram = stats.get('ram_mb', 0)
        
        if status == 'Running':
            self.lbl_status.configure(text="● ACTIVE", text_color="#4ade80")
            self.btn_run.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.btn_restart.configure(state="normal")
            
            self.lbl_cpu.configure(text=f"CPU: {cpu:.1f}%")
            self.lbl_ram.configure(text=f"RAM: {ram:.0f} MB")
            
            # RAM Alert Logic
            if ram > 500:
                self.lbl_ram.configure(text_color="orange")
            else:
                self.lbl_ram.configure(text_color="gray90")
                
        else:
            self.lbl_status.configure(text="○ STOPPED", text_color="grey")
            self.btn_run.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.btn_restart.configure(state="disabled")
            self.lbl_cpu.configure(text="CPU: -")
            self.lbl_ram.configure(text="RAM: -")


class AppHub(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.manager = AppManager()
        self.title("Antigravity App Hub & Monitor")
        self.geometry("800x600")
        
        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        self.header = ctk.CTkFrame(self, height=60, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        
        self.lbl_logo = ctk.CTkLabel(self.header, text="🛸 Antigravity Hub", font=("Roboto Black", 24))
        self.lbl_logo.pack(side="left", padx=20, pady=10)
        
        self.btn_kill_all = ctk.CTkButton(self.header, text="☠ KILL ALL PROCESSES", fg_color="darkred", hover_color="#500000", command=self.kill_all)
        self.btn_kill_all.pack(side="right", padx=20)
        
        # Content
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        
        self.cards = {}
        for app in APPS_CONFIG:
            card = AppCard(self.scroll_frame, app['name'], app['icon'], self.manager)
            card.pack(fill="x", pady=10)
            self.cards[app['name']] = card
            
        # Footer
        self.footer = ctk.CTkLabel(self, text="Auto-Polling: Enabled (2s)", text_color="grey")
        self.footer.grid(row=2, column=0, pady=5)
        
        # Start Polling
        self.running = True
        self.poll_thread = threading.Thread(target=self.poll_stats, daemon=True)
        self.poll_thread.start()
        
    def kill_all(self):
        self.manager.kill_all()
        
    def poll_stats(self):
        while self.running:
            try:
                stats = self.manager.get_stats()
                # Update UI thread-safely? CustomTkinter usually handles update_idletasks well
                # but direct widget config from thread can be risky. 
                # CTK is generally thread-safe for config, but let's be careful.
                for name, data in stats.items():
                    if name in self.cards:
                        self.cards[name].update_state(data)
            except Exception as e:
                print(f"Polling error: {e}")
                
            time.sleep(2)

if __name__ == "__main__":
    app = AppHub()
    app.mainloop()
