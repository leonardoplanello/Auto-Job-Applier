import sqlite3
import os
import sys
import argparse
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

# Resolve DB path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "user_data", "app.db")

def fetch_initial_logs(db_path, session_id=None, limit=200):
    if not os.path.exists(db_path):
        return [], 0, session_id
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='log_entries'")
        if not cursor.fetchone():
            conn.close()
            return [], 0, session_id
            
        # If no session_id is provided, get the latest session_id
        if not session_id:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
            if cursor.fetchone():
                cursor.execute("SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    session_id = row[0]
                
        if session_id:
            query = """
                SELECT id, timestamp, level, category, message, company, job_title 
                FROM log_entries 
                WHERE session_id = ? 
                ORDER BY id DESC LIMIT ?
            """
            cursor.execute(query, (session_id, limit))
        else:
            query = """
                SELECT id, timestamp, level, category, message, company, job_title 
                FROM log_entries 
                ORDER BY id DESC LIMIT ?
            """
            cursor.execute(query, (limit,))
            
        rows = cursor.fetchall()
        conn.close()
        
        rows.reverse()
        max_id = max([r[0] for r in rows]) if rows else 0
        return rows, max_id, session_id
    except Exception as e:
        print(f"Error fetching logs: {e}")
        return [], 0, session_id

def fetch_new_logs(db_path, session_id, last_id):
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='log_entries'")
        if not cursor.fetchone():
            conn.close()
            return []
            
        if session_id:
            query = """
                SELECT id, timestamp, level, category, message, company, job_title 
                FROM log_entries 
                WHERE session_id = ? AND id > ? 
                ORDER BY id ASC
            """
            cursor.execute(query, (session_id, last_id))
        else:
            query = """
                SELECT id, timestamp, level, category, message, company, job_title 
                FROM log_entries 
                WHERE id > ? 
                ORDER BY id ASC
            """
            cursor.execute(query, (last_id,))
            
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error fetching new logs: {e}")
        return []

class LogWindow:
    def __init__(self, root, session_id=None):
        self.root = root
        self.session_id = session_id
        self.db_path = DB_PATH
        
        self.all_logs = []
        self.last_id = 0
        self.filter_level = "All"
        self.search_term = ""
        self.auto_scroll = tk.BooleanVar(value=True)
        
        # Set window properties
        self.root.title("Auto J*b Applier — Real-time Logs")
        self.root.geometry("800x600")
        self.root.configure(bg="#0f172a") # Slate 900
        
        # Center the window slightly
        try:
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x = (screen_width - 800) // 2
            y = (screen_height - 600) // 2
            self.root.geometry(f"800x600+{x}+{y}")
        except Exception:
            pass
            
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.setup_styles()
        self.create_widgets()
        self.load_initial_logs()
        self.poll()

    def setup_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # Style Combobox dropdowns to fit dark theme
        style.configure("TCombobox", fieldbackground="#1e293b", background="#0f172a", foreground="#f8fafc", arrowcolor="#f8fafc")

    def create_widgets(self):
        # Top filter bar
        filter_frame = tk.Frame(self.root, bg="#0f172a", padx=15, pady=12)
        filter_frame.pack(fill=tk.X)
        
        # Level filter label & combobox
        lbl_level = tk.Label(filter_frame, text="Filter Level:", bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 9, "bold"))
        lbl_level.pack(side=tk.LEFT, padx=(0, 6))
        
        self.cb_level = ttk.Combobox(filter_frame, values=["All", "Success", "Info", "Warning", "Error", "Action", "Debug"], width=10, state="readonly")
        self.cb_level.set("All")
        self.cb_level.pack(side=tk.LEFT, padx=(0, 20))
        self.cb_level.bind("<<ComboboxSelected>>", self.on_level_changed)
        
        # Search label & entry
        lbl_search = tk.Label(filter_frame, text="Search Message:", bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 9, "bold"))
        lbl_search.pack(side=tk.LEFT, padx=(0, 6))
        
        self.ent_search = tk.Entry(filter_frame, bg="#1e293b", fg="#f8fafc", insertbackground="#f8fafc", relief=tk.FLAT, font=("Segoe UI", 10), width=28)
        self.ent_search.pack(side=tk.LEFT, padx=(0, 20))
        self.ent_search.bind("<KeyRelease>", self.on_search_changed)
        
        # Auto scroll checkbutton
        self.chk_scroll = tk.Checkbutton(
            filter_frame, 
            text="Auto-scroll", 
            variable=self.auto_scroll,
            bg="#0f172a", 
            fg="#94a3b8", 
            selectcolor="#0f172a",
            activebackground="#0f172a",
            activeforeground="#f8fafc",
            font=("Segoe UI", 9)
        )
        self.chk_scroll.pack(side=tk.LEFT)
        
        # Clear button
        btn_clear = tk.Button(
            filter_frame, 
            text="Clear View", 
            command=self.clear_view,
            bg="#3b82f6", 
            fg="white", 
            activebackground="#2563eb", 
            activeforeground="white",
            relief=tk.FLAT, 
            font=("Segoe UI", 9, "bold"), 
            padx=12,
            pady=3
        )
        btn_clear.pack(side=tk.RIGHT)
        
        # Logs Display Area (ScrolledText)
        self.text_area = ScrolledText(
            self.root, 
            bg="#1e293b", 
            fg="#f8fafc", 
            font=("Consolas", 10), 
            wrap=tk.WORD, 
            relief=tk.FLAT, 
            padx=12, 
            pady=12
        )
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))
        self.text_area.configure(state=tk.DISABLED)
        
        # Status bar
        self.status_bar = tk.Frame(self.root, bg="#0f172a", height=28, padx=15)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 5))
        
        self.lbl_status_session = tk.Label(self.status_bar, text="Session: Connecting...", bg="#0f172a", fg="#64748b", font=("Segoe UI", 9))
        self.lbl_status_session.pack(side=tk.LEFT)
        
        self.lbl_status_count = tk.Label(self.status_bar, text="Logs: 0", bg="#0f172a", fg="#64748b", font=("Segoe UI", 9))
        self.lbl_status_count.pack(side=tk.RIGHT)
        
        # Define Text Tags for level-specific styling
        self.text_area.tag_config("timestamp", foreground="#64748b")
        self.text_area.tag_config("category", foreground="#94a3b8", font=("Consolas", 10, "italic"))
        self.text_area.tag_config("info", foreground="#60a5fa")     # Blue
        self.text_area.tag_config("success", foreground="#34d399", font=("Consolas", 10, "bold"))  # Emerald Green
        self.text_area.tag_config("warning", foreground="#fbbf24", font=("Consolas", 10, "bold"))  # Amber
        self.text_area.tag_config("error", foreground="#f87171", font=("Consolas", 10, "bold"))    # Red
        self.text_area.tag_config("action", foreground="#c084fc")   # Purple
        self.text_area.tag_config("debug", foreground="#94a3b8")    # Slate Gray
        self.text_area.tag_config("meta", foreground="#e2e8f0")     # Light text for Company/Job details

    def load_initial_logs(self):
        rows, max_id, resolved_session_id = fetch_initial_logs(self.db_path, self.session_id)
        self.session_id = resolved_session_id
        self.last_id = max_id
        self.all_logs = rows
        
        sess_display = self.session_id if self.session_id else "All Sessions"
        if len(sess_display) > 36:
            sess_display = sess_display[:33] + "..."
        self.lbl_status_session.config(text=f"Session ID: {sess_display}")
        
        self.render_logs_view()

    def render_logs_view(self):
        self.text_area.configure(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)
        
        filtered_count = 0
        for log in self.all_logs:
            if self.insert_log_row(log):
                filtered_count += 1
                
        self.text_area.configure(state=tk.DISABLED)
        self.lbl_status_count.config(text=f"Logs: {filtered_count} displayed / {len(self.all_logs)} total")
        if self.auto_scroll.get():
            self.text_area.see(tk.END)

    def insert_log_row(self, log):
        _, timestamp, level, category, message, company, job_title = log
        
        lvl_lower = level.lower()
        if self.filter_level != "All" and self.filter_level.lower() != lvl_lower:
            return False
            
        combined_text = f"{message} {company or ''} {job_title or ''} {category or ''}".lower()
        if self.search_term and self.search_term not in combined_text:
            return False
            
        try:
            if isinstance(timestamp, str):
                # Handle formats like YYYY-MM-DD HH:MM:SS.mmmmmm or with T / Z
                ts_clean = timestamp.replace("T", " ").replace("Z", "")
                dt = datetime.fromisoformat(ts_clean.split(".")[0])
            else:
                dt = timestamp
            ts_str = dt.strftime("%H:%M:%S")
        except Exception:
            ts_str = str(timestamp)[:19]
            
        self.text_area.insert(tk.END, f"[{ts_str}] ", "timestamp")
        if category:
            self.text_area.insert(tk.END, f"[{category.upper()}] ", "category")
            
        if company or job_title:
            parts = []
            if job_title: parts.append(job_title)
            if company: parts.append(company)
            meta_str = f"({ ' | '.join(parts) }) "
            self.text_area.insert(tk.END, meta_str, "meta")
            
        self.text_area.insert(tk.END, f"{message}\n", lvl_lower)
        return True

    def poll(self):
        try:
            if self.session_id:
                new_rows = fetch_new_logs(self.db_path, self.session_id, self.last_id)
            else:
                new_rows = fetch_new_logs(self.db_path, None, self.last_id)
                
            if new_rows:
                self.text_area.configure(state=tk.NORMAL)
                for log in new_rows:
                    self.all_logs.append(log)
                    self.insert_log_row(log)
                self.last_id = max([r[0] for r in new_rows])
                self.text_area.configure(state=tk.DISABLED)
                
                self.render_logs_view()  # Re-render to ensure correct counts and filters
        except Exception as e:
            print(f"Polling error: {e}")
            
        # Poll again in 500ms
        self.root.after(500, self.poll)

    def on_level_changed(self, event):
        self.filter_level = self.cb_level.get()
        self.render_logs_view()

    def on_search_changed(self, event):
        self.search_term = self.ent_search.get().lower()
        self.render_logs_view()

    def clear_view(self):
        self.all_logs = []
        self.text_area.configure(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)
        self.text_area.configure(state=tk.DISABLED)
        self.lbl_status_count.config(text="Logs: 0 displayed / 0 total")

    def on_close(self):
        self.root.destroy()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto J*b Applier real-time log viewer.")
    parser.add_argument("--session-id", type=str, help="ID of the session to view logs for.")
    args = parser.parse_args()
    
    root = tk.Tk()
    app = LogWindow(root, session_id=args.session_id)
    root.mainloop()
