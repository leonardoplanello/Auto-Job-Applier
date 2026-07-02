import tkinter as tk
from tkinter import ttk
from typing import Tuple, Any, Optional
import re

def deduplicate_string(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    
    # 1. Normalize whitespaces to single space
    normalized = " ".join(text.split())
    
    # 2. Check word-level split halves
    words = normalized.split()
    n_words = len(words)
    if n_words >= 2:
        for half in range(n_words // 2, 0, -1):
            part1 = " ".join(words[:half])
            part2 = " ".join(words[half:2*half])
            
            norm1 = re.sub(r'[^a-zA-Z0-9]', '', part1).lower()
            norm2 = re.sub(r'[^a-zA-Z0-9]', '', part2).lower()
            
            if norm1 == norm2 and norm1:
                remaining = words[2*half:]
                if remaining:
                    return part1 + " " + " ".join(remaining)
                return part1

    # 3. Check character-level split halves
    n_chars = len(normalized)
    for half_len in range(n_chars // 2, 2, -1):
        part1 = normalized[:half_len].strip()
        part2 = normalized[half_len:2*half_len].strip()
        
        norm1 = re.sub(r'[^a-zA-Z0-9]', '', part1).lower()
        norm2 = re.sub(r'[^a-zA-Z0-9]', '', part2).lower()
        
        if norm1 == norm2 and norm1:
            remaining = normalized[2*half_len:].strip()
            if remaining:
                return part1 + " " + remaining
            return part1
            
    return text

active_root: Optional[tk.Tk] = None

def close_active_root():
    global active_root
    if active_root:
        try:
            active_root.after(0, active_root.destroy)
        except Exception:
            pass
        active_root = None

def show_desktop_popup(payload: dict) -> Tuple[Any, bool]:
    """
    Displays a modal Tkinter dialog on the local desktop to gather user input.
    Blocks the calling thread until user interaction is complete.
    Returns:
        (answer, save_in_db)
    """
    global active_root
    # Initialize response values
    response = {"answer": None, "save": True}

    # Create Tkinter root window
    root = tk.Tk()
    active_root = root
    root.title("Auto J*b Applier")
    
    # Calculate position for bottom-right corner of the primary screen
    window_width = 520
    window_height = 400
    if payload.get("type") == "review_submit":
        window_height = 640
    elif payload.get("type") == "question_checkbox" and payload.get("options"):
        window_height = 500

    if payload.get("error_message"):
        window_height += 80
    try:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        # Offset slightly from the bottom-right to clear taskbar and padding
        x = max(0, screen_width - window_width - 20)
        y = max(0, screen_height - window_height - 60)
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    except Exception:
        root.geometry(f"{window_width}x{window_height}")
        
    root.minsize(450, 300)
    root.configure(bg="#f8fafc")  # Slate 50 background

    # Force window to the front
    root.lift()
    root.attributes("-topmost", True)
    # Give focus to the window
    root.focus_force()

    # Style configuration
    style = ttk.Style(root)
    # Try using 'vista' or 'xpnative' or 'clam' for clean theme on Windows
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Color Constants
    bg_color = "#f8fafc"
    text_color = "#1e293b"      # Slate 800
    primary_color = "#0b7ae8"   # Custom Theme Blue
    primary_active = "#025eb2"  # Darker Blue
    sec_bg = "#f1f5f9"          # Slate 100
    sec_text = "#475569"        # Slate 600

    style.configure(".", background=bg_color, foreground=text_color)
    style.configure("TLabel", font=("Segoe UI", 10), background=bg_color, foreground=text_color)
    style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), background=bg_color, foreground="#0f172a")
    style.configure("Meta.TLabel", font=("Segoe UI", 9, "semibold"), background=bg_color, foreground=primary_color)
    style.configure("Question.TLabel", font=("Segoe UI", 10, "bold"), background=bg_color, foreground=text_color)
    style.configure("JobTitle.TLabel", font=("Segoe UI", 10, "bold"), background=bg_color, foreground=text_color)
    style.configure("JobTitleLarge.TLabel", font=("Segoe UI", 13, "bold"), background=bg_color, foreground=text_color)
    style.configure("Company.TLabel", font=("Segoe UI", 9.5), background=bg_color, foreground=sec_text)
    
    # Checkbox style
    style.configure("TCheckbutton", font=("Segoe UI", 9), background=bg_color, foreground="#475569")
    
    # Button styles
    style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=primary_color, foreground="white", borderwidth=0)
    style.map("Primary.TButton", background=[("active", primary_active)], foreground=[("active", "white")])
    
    style.configure("Secondary.TButton", font=("Segoe UI", 10, "bold"), background="#e2e8f0", foreground="#334155", borderwidth=0)
    style.map("Secondary.TButton", background=[("active", "#cbd5e1")], foreground=[("active", "#1e293b")])

    # Card styles for review_submit
    style.configure("Card.TFrame", background="#ffffff")
    style.configure("Card.TLabel", background="#ffffff", foreground=text_color)
    style.configure("CardHeader.TLabel", background="#ffffff", font=("Segoe UI", 9, "bold"), foreground=text_color)
    style.configure("CardMeta.TLabel", background="#ffffff", font=("Segoe UI", 8, "bold"), foreground=primary_color)
    style.configure("Card.TCheckbutton", font=("Segoe UI", 9), background="#ffffff", foreground="#475569")

    # Main container frame with padding
    main_frame = ttk.Frame(root, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Footer Buttons Layout (pack first at the bottom so it stays visible)
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

    # Toolbar frame for actions
    toolbar_frame = ttk.Frame(main_frame)
    toolbar_frame.pack(fill=tk.X, pady=(0, 10))

    # Job context variables
    company = payload.get("company")
    job_title = payload.get("job_title")
    job_url = payload.get("job_url")

    # Clean job title and company from duplicate newlines (if any)
    if job_title and isinstance(job_title, str):
        job_title = job_title.split("\n")[0].strip()
    if company and isinstance(company, str):
        company = company.split("\n")[0].strip()

    def stop_bot_action():
        response["answer"] = "__stop_bot__"
        response["save"] = False
        root.destroy()
        
    def go_dashboard_action():
        import webbrowser
        webbrowser.open("http://localhost:5173")
        root.iconify()
        
    def view_job_action():
        import webbrowser
        if job_url:
            webbrowser.open(job_url)

    # Style for toolbar buttons
    style.configure("Toolbar.TButton", font=("Segoe UI", 8), padding=2)

    stop_btn = ttk.Button(toolbar_frame, text="⏹ Stop Bot", command=stop_bot_action, style="Toolbar.TButton")
    stop_btn.pack(side=tk.RIGHT, padx=(5, 0))
    
    dash_btn = ttk.Button(toolbar_frame, text="🏠 Dashboard", command=go_dashboard_action, style="Toolbar.TButton")
    dash_btn.pack(side=tk.RIGHT, padx=(5, 0))
    
    # Show "View Job" button if we have any job context (title, company, or url)
    if job_title or company or job_url:
        job_btn = ttk.Button(toolbar_frame, text="🔗 View Job", command=view_job_action, style="Toolbar.TButton")
        if not job_url:
            job_btn.configure(state="disabled")
        job_btn.pack(side=tk.RIGHT, padx=(5, 0))

    # Below toolbar: Job Title and Company name
    if job_title:
        job_title_lbl = ttk.Label(main_frame, text=job_title, style="JobTitleLarge.TLabel", wraplength=480)
        job_title_lbl.pack(anchor=tk.W, pady=(5, 2))

    if company:
        company_lbl = ttk.Label(main_frame, text=company, style="Company.TLabel", wraplength=480)
        company_lbl.pack(anchor=tk.W, pady=(0, 10))

    # Main Title
    title = payload.get("title", "Action Required")
    if title and title not in ["New Question", "Numerical Answer", "Choose an option"]:
        title_lbl = ttk.Label(main_frame, text=title, style="Header.TLabel", wraplength=480)
        title_lbl.pack(anchor=tk.W, pady=(0, 10))

    # Divider line
    divider = ttk.Separator(main_frame, orient="horizontal")
    divider.pack(fill=tk.X, pady=(0, 15))

    # Display validation error message if present
    error_msg = payload.get("error_message")
    if error_msg:
        err_frame = tk.Frame(main_frame, bg="#fef2f2", highlightbackground="#fca5a5", highlightthickness=1, bd=0)
        err_frame.pack(fill=tk.X, pady=(0, 15), ipady=5, ipadx=5)
        err_lbl_title = tk.Label(err_frame, text="⚠️ Validation Error:", font=("Segoe UI", 9, "bold"), bg="#fef2f2", fg="#b91c1c", anchor="w")
        err_lbl_title.pack(fill=tk.X, padx=5, pady=(2, 0))
        err_lbl_text = tk.Label(err_frame, text=error_msg, font=("Segoe UI", 9), bg="#fef2f2", fg="#7f1d1d", anchor="w", wraplength=450, justify="left")
        err_lbl_text.pack(fill=tk.X, padx=5, pady=(0, 2))

    popup_type = payload.get("type", "question_text")

    raw_question = payload.get("question")
    cleaned_question = deduplicate_string(raw_question) if raw_question else ""

    raw_message = payload.get("message")
    cleaned_message = deduplicate_string(raw_message) if raw_message else ""

    # Form field controls (defined based on type)
    entry_widget = None
    save_var = tk.BooleanVar(value=True)

    # Default actions to prevent UnboundLocalError
    def default_confirm():
        response["answer"] = True
        response["save"] = False
        root.destroy()

    def default_skip():
        response["answer"] = "__skip_job__"
        response["save"] = False
        root.destroy()

    confirm_action = default_confirm
    skip_action = default_skip

    # 1. QUESTION TEXT
    if popup_type == "question_text":
        q_lbl = ttk.Label(main_frame, text=cleaned_question or "Please answer the following question:", style="Question.TLabel", wraplength=480)
        q_lbl.pack(anchor=tk.W, pady=(0, 8))
        
        entry_widget = tk.Text(main_frame, height=5, font=("Segoe UI", 10), wrap=tk.WORD, relief=tk.SOLID, bd=1, highlightthickness=0)
        entry_widget.pack(fill=tk.X, pady=(0, 10))
        
        default_val = payload.get("current_value") or payload.get("value") or payload.get("default") or ""
        if default_val:
            entry_widget.insert(tk.END, str(default_val))
            
        entry_widget.focus_set()

        chk = ttk.Checkbutton(main_frame, text="Remember this answer (save in Q&A Bank)", variable=save_var, style="TCheckbutton")
        chk.pack(anchor=tk.W, pady=(5, 15))

        def on_confirm():
            response["answer"] = entry_widget.get("1.0", tk.END).strip()
            response["save"] = save_var.get()
            root.destroy()

        def on_skip():
            response["answer"] = "__skip_job__"
            response["save"] = False
            root.destroy()

        confirm_action = on_confirm
        skip_action = on_skip

    # 2. QUESTION NUMBER
    elif popup_type == "question_number":
        q_lbl = ttk.Label(main_frame, text=cleaned_question or "Please enter a numerical value:", style="Question.TLabel", wraplength=480)
        q_lbl.pack(anchor=tk.W, pady=(0, 8))

        min_val = payload.get("min", 0)
        max_val = payload.get("max", 999999)
        
        default_val = payload.get("current_value") or payload.get("value") or payload.get("default") or min_val
        entry_var = tk.StringVar(value=str(default_val))
        entry_widget = ttk.Spinbox(main_frame, from_=min_val, to=max_val, textvariable=entry_var, font=("Segoe UI", 10))
        entry_widget.pack(fill=tk.X, pady=(0, 10))
        entry_widget.focus_set()

        chk = ttk.Checkbutton(main_frame, text="Remember this answer (save in Q&A Bank)", variable=save_var, style="TCheckbutton")
        chk.pack(anchor=tk.W, pady=(5, 15))

        def on_confirm():
            val_str = entry_var.get().strip()
            try:
                response["answer"] = int(val_str)
            except ValueError:
                response["answer"] = 0
            response["save"] = save_var.get()
            root.destroy()

        def on_skip():
            response["answer"] = "__skip_job__"
            response["save"] = False
            root.destroy()

        confirm_action = on_confirm
        skip_action = on_skip

    # 3. QUESTION SELECT
    elif popup_type == "question_select":
        q_lbl = ttk.Label(main_frame, text=cleaned_question or "Choose an option:", style="Question.TLabel", wraplength=480)
        q_lbl.pack(anchor=tk.W, pady=(0, 8))

        options = payload.get("options", [])
        default_val = payload.get("current_value") or payload.get("value") or payload.get("default")
        if default_val and default_val in options:
            combo_var = tk.StringVar(value=default_val)
        else:
            combo_var = tk.StringVar(value=options[0] if options else "")
        entry_widget = ttk.Combobox(main_frame, textvariable=combo_var, values=options, state="readonly", font=("Segoe UI", 10))
        entry_widget.pack(fill=tk.X, pady=(0, 10))
        entry_widget.focus_set()

        chk = ttk.Checkbutton(main_frame, text="Remember this answer (save in Q&A Bank)", variable=save_var, style="TCheckbutton")
        chk.pack(anchor=tk.W, pady=(5, 15))

        def on_confirm():
            response["answer"] = combo_var.get()
            response["save"] = save_var.get()
            root.destroy()

        def on_skip():
            response["answer"] = "__skip_job__"
            response["save"] = False
            root.destroy()

        confirm_action = on_confirm
        skip_action = on_skip

    # 4. MANUAL ACTION
    elif popup_type == "manual_action":
        msg_lbl = ttk.Label(main_frame, text=cleaned_message or "Please perform manual action.", wraplength=480, justify=tk.LEFT)
        msg_lbl.pack(anchor=tk.W, fill=tk.BOTH, expand=True, pady=(0, 15))

        def on_confirm():
            response["answer"] = True
            response["save"] = False
            root.destroy()

        def on_skip():
            response["answer"] = False
            response["save"] = False
            root.destroy()

        confirm_action = on_confirm
        skip_action = on_skip

    elif popup_type == "confirm_message":
        # Recruiter details labels
        recruiter_info = f"Recruiter: {payload.get('recruiter_name', 'Recruiter')} ({payload.get('connection_status', 'unknown')} degree)\n"
        recruiter_info += f"Company: {payload.get('company', 'Company')} | Job: {payload.get('job_title', 'Job')}"
        
        info_lbl = ttk.Label(main_frame, text=recruiter_info, style="Company.TLabel", justify=tk.LEFT)
        info_lbl.pack(anchor=tk.W, pady=(0, 10))
        
        q_lbl = ttk.Label(main_frame, text="Message Body (Editable):", style="Question.TLabel")
        q_lbl.pack(anchor=tk.W, pady=(0, 4))
        
        # Scrolled Text Box
        import tkinter.scrolledtext as st
        text_box = st.ScrolledText(main_frame, width=55, height=10, font=("Segoe UI", 10))
        text_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_box.insert(tk.INSERT, payload.get("current_value", ""))
        entry_widget = text_box
        
        def on_confirm():
            response["answer"] = text_box.get("1.0", tk.END).strip()
            response["save"] = True
            root.destroy()
            
        def on_skip():
            response["answer"] = None
            response["save"] = False
            root.destroy()
            
        confirm_action = on_confirm
        skip_action = on_skip

    elif popup_type == "confirm_email":
        recruiter_info = f"Recruiter: {payload.get('recruiter_name', 'Recruiter')} | Email: {payload.get('email', '')}\n"
        recruiter_info += f"Company: {payload.get('company', 'Company')} | Job: {payload.get('job_title', 'Job')}"
        
        info_lbl = ttk.Label(main_frame, text=recruiter_info, style="Company.TLabel", justify=tk.LEFT)
        info_lbl.pack(anchor=tk.W, pady=(0, 10))
        
        sub_lbl = ttk.Label(main_frame, text="Subject:", style="Question.TLabel")
        sub_lbl.pack(anchor=tk.W, pady=(0, 2))
        
        sub_entry = ttk.Entry(main_frame, font=("Segoe UI", 10))
        sub_entry.pack(fill=tk.X, pady=(0, 8))
        sub_entry.insert(0, payload.get("subject", ""))
        
        body_lbl = ttk.Label(main_frame, text="Email Body (Editable):", style="Question.TLabel")
        body_lbl.pack(anchor=tk.W, pady=(0, 2))
        
        import tkinter.scrolledtext as st
        text_box = st.ScrolledText(main_frame, width=55, height=8, font=("Segoe UI", 10))
        text_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_box.insert(tk.INSERT, payload.get("current_value", ""))
        entry_widget = text_box
        
        def on_confirm():
            response["answer"] = {
                "subject": sub_entry.get().strip(),
                "body": text_box.get("1.0", tk.END).strip()
            }
            response["save"] = True
            root.destroy()
            
        def on_skip():
            response["answer"] = None
            response["save"] = False
            root.destroy()
            
        confirm_action = on_confirm
        skip_action = on_skip

    # 6. QUESTION FILE (Upload Files)
    elif popup_type == "question_file":
        q_lbl = ttk.Label(main_frame, text=cleaned_question or "Please select a file:", style="Question.TLabel", wraplength=480)
        q_lbl.pack(anchor=tk.W, pady=(0, 8))
        
        file_hint = payload.get("file_hint", "")
        if file_hint:
            hint_lbl = ttk.Label(main_frame, text=f"Requirements: {file_hint}", style="Meta.TLabel", wraplength=480)
            hint_lbl.pack(anchor=tk.W, pady=(0, 8))

        path_var = tk.StringVar()
        
        options = payload.get("options", [])
        if options:
            opt_lbl = ttk.Label(main_frame, text="Select a file already on LinkedIn:", style="Meta.TLabel", wraplength=480)
            opt_lbl.pack(anchor=tk.W, pady=(0, 5))
            
            combo_var = tk.StringVar()
            combo = ttk.Combobox(main_frame, textvariable=combo_var, values=options, state="readonly", font=("Segoe UI", 9))
            combo.pack(fill=tk.X, pady=(0, 10))
            
            def on_combo_select(event):
                path_var.set(f"__use_linkedin_file__:{combo_var.get()}")
            combo.bind("<<ComboboxSelected>>", on_combo_select)
            
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        entry_widget = ttk.Entry(file_frame, textvariable=path_var, font=("Segoe UI", 10), state="normal")
        entry_widget.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def browse_file():
            from tkinter import filedialog
            selected_file = filedialog.askopenfilename(
                title=payload.get("question", "Select File"),
                filetypes=[
                    ("Supported files", "*.pdf;*.doc;*.docx;*.txt;*.jpg;*.jpeg;*.png;*.gif;*.JPG;*.JPEG;*.PNG;*.GIF"),
                    ("All files", "*.*")
                ]
            )
            if selected_file:
                path_var.set(selected_file)
                
        browse_btn = ttk.Button(file_frame, text="Browse...", command=browse_file, style="Secondary.TButton")
        browse_btn.pack(side=tk.RIGHT)

        # Hook drag and drop if windnd is available
        try:
            import windnd
            def on_file_dropped(files):
                if files:
                    fpath = files[0]
                    if isinstance(fpath, bytes):
                        fpath = fpath.decode('utf-8')
                    fpath = fpath.strip()
                    if fpath.startswith('"') and fpath.endswith('"'):
                        fpath = fpath[1:-1].strip()
                    elif fpath.startswith("'") and fpath.endswith("'"):
                        fpath = fpath[1:-1].strip()
                    path_var.set(fpath)
            windnd.hook_dropfiles(root, on_file_dropped)
        except Exception:
            pass

        def on_confirm():
            val = path_var.get().strip()
            # Strip quotes if copied from Explorer
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1].strip()
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1].strip()
                
            if not val:
                from tkinter import messagebox
                messagebox.showwarning("File Required", "Please select or paste a file path first.")
                return
                
            import os
            if not val.startswith("__use_linkedin_file__:") and not os.path.exists(val):
                from tkinter import messagebox
                messagebox.showwarning("File Not Found", f"The file path does not exist:\n{val}")
                return
                
            response["answer"] = val
            response["save"] = False
            root.destroy()

        def on_skip():
            response["answer"] = "__skip_job__"
            response["save"] = False
            root.destroy()

        confirm_action = on_confirm
        skip_action = on_skip

    # 8. QUESTION CHECKBOX
    elif popup_type == "question_checkbox":
        q_lbl = ttk.Label(main_frame, text=cleaned_question or "Check the option:", style="Question.TLabel", wraplength=480)
        q_lbl.pack(anchor=tk.W, pady=(0, 8))
        
        options = payload.get("options", [])
        if options:
            import json
            selected_opts = []
            default_val = payload.get("current_value") or payload.get("value") or payload.get("default")
            if default_val:
                if isinstance(default_val, list):
                    selected_opts = [str(v).strip().lower() for v in default_val]
                elif isinstance(default_val, str):
                    try:
                        parsed = json.loads(default_val)
                        if isinstance(parsed, list):
                            selected_opts = [str(v).strip().lower() for v in parsed]
                        else:
                            selected_opts = [str(parsed).strip().lower()]
                    except json.JSONDecodeError:
                        if default_val.startswith("[") and default_val.endswith("]"):
                            items = default_val[1:-1].split(",")
                            for item in items:
                                item = item.strip().strip("'\"")
                                if item:
                                    selected_opts.append(item.lower())
                        else:
                            selected_opts = [v.strip().lower() for v in default_val.split(",") if v.strip()]
            
            # Scrollable checklist container
            container = ttk.Frame(main_frame)
            container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            canvas = tk.Canvas(container, bg="#ffffff", bd=0, highlightthickness=0)
            scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas, style="Card.TFrame") # White background matching canvas
            
            def configure_window(event):
                canvas.itemconfig(canvas_window, width=event.width)
            
            canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.bind("<Configure>", configure_window)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            canvas.bind("<MouseWheel>", _on_mousewheel)
            scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
            
            cb_vars = []
            for opt in options:
                is_opt_checked = opt.strip().lower() in selected_opts
                var = tk.BooleanVar(value=is_opt_checked)
                cb_vars.append((opt, var))
                chk_btn = ttk.Checkbutton(scrollable_frame, text=opt, variable=var, style="Card.TCheckbutton")
                chk_btn.pack(anchor=tk.W, pady=4, padx=8)
                chk_btn.bind("<MouseWheel>", _on_mousewheel)
            
            chk = ttk.Checkbutton(main_frame, text="Remember this answer (save in Q&A Bank)", variable=save_var, style="TCheckbutton")
            chk.pack(anchor=tk.W, pady=(5, 15))
            
            def on_confirm():
                selected = [opt for opt, var in cb_vars if var.get()]
                response["answer"] = selected
                response["save"] = save_var.get()
                root.destroy()
        else:
            default_val = payload.get("current_value") or payload.get("value") or payload.get("default") or "No"
            is_checked = str(default_val).lower() in ["true", "yes", "1", "checked"]
            
            cb_var = tk.BooleanVar(value=is_checked)
            chk_btn = ttk.Checkbutton(main_frame, text="Yes / Checked", variable=cb_var, style="TCheckbutton")
            chk_btn.pack(anchor=tk.W, pady=(0, 15))
            chk_btn.focus_set()
            
            chk = ttk.Checkbutton(main_frame, text="Remember this answer (save in Q&A Bank)", variable=save_var, style="TCheckbutton")
            chk.pack(anchor=tk.W, pady=(5, 15))
            
            def on_confirm():
                response["answer"] = "Yes" if cb_var.get() else "No"
                response["save"] = save_var.get()
                root.destroy()

        def on_skip():
            response["answer"] = "__skip_job__"
            response["save"] = False
            root.destroy()

        confirm_action = on_confirm
        skip_action = on_skip

    # 7. REVIEW SUBMIT
    elif popup_type == "review_submit":
        msg_lbl = ttk.Label(main_frame, text=cleaned_message or "Please review the information filled by the bot below. You can edit any field before submitting.", wraplength=480, justify=tk.LEFT)
        msg_lbl.pack(anchor=tk.W, fill=tk.X, pady=(0, 10))

        # Create canvas and scrollbar for fields
        container = ttk.Frame(main_frame)
        container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        canvas = tk.Canvas(container, bg="#f8fafc", bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def configure_window(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", configure_window)
        
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)

        fields = payload.get("fields", [])
        field_vars = {} # Maps field label to its Tkinter Variable or Widget

        for idx, field in enumerate(fields):
            label_text = field.get("label", f"Field {idx}")
            label_text = deduplicate_string(label_text)
            field_value = field.get("value", "")
            if field_value is None:
                field_value = ""
            field_type = field.get("field_type", "text")
            options = field.get("options", [])
            source = field.get("source", "")

            # Create a card frame for each field
            card = ttk.Frame(scrollable_frame, padding=10, style="Card.TFrame")
            card.pack(fill=tk.X, pady=(0, 8), padx=4)

            # Label frame for the header of the card (displays name and source)
            lbl_frame = ttk.Frame(card, style="Card.TFrame")
            lbl_frame.pack(fill=tk.X, pady=(0, 4))

            # Header style
            header_lbl = ttk.Label(lbl_frame, text=label_text, style="CardHeader.TLabel", wraplength=420, justify=tk.LEFT)
            header_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            if source and source.lower() != "user_edit":
                source_lbl = ttk.Label(lbl_frame, text=source.upper(), style="CardMeta.TLabel")
                source_lbl.pack(side=tk.RIGHT, padx=(5, 0))

            # Input widget
            if field_type == "checkbox":
                if options:
                    import json
                    selected_opts = []
                    if field_value:
                        if isinstance(field_value, list):
                            selected_opts = [str(v).strip().lower() for v in field_value]
                        elif isinstance(field_value, str):
                            try:
                                parsed = json.loads(field_value)
                                if isinstance(parsed, list):
                                    selected_opts = [str(v).strip().lower() for v in parsed]
                                else:
                                    selected_opts = [str(parsed).strip().lower()]
                            except json.JSONDecodeError:
                                if field_value.startswith("[") and field_value.endswith("]"):
                                    items = field_value[1:-1].split(",")
                                    for item in items:
                                        item = item.strip().strip("'\"")
                                        if item:
                                            selected_opts.append(item.lower())
                                else:
                                    selected_opts = [v.strip().lower() for v in field_value.split(",") if v.strip()]
                    
                    cb_vars = []
                    for opt in options:
                        is_opt_checked = opt.strip().lower() in selected_opts
                        var = tk.BooleanVar(value=is_opt_checked)
                        cb_vars.append((opt, var))
                        chk_btn = ttk.Checkbutton(card, text=opt, variable=var, style="Card.TCheckbutton")
                        chk_btn.pack(anchor=tk.W, pady=2)
                    field_vars[label_text] = ("checklist", cb_vars)
                else:
                    is_checked = str(field_value).lower() in ["true", "yes", "1", "checked"]
                    var = tk.BooleanVar(value=is_checked)
                    field_vars[label_text] = (field_type, var)
                    
                    chk_btn = ttk.Checkbutton(card, text="Yes / Checked", variable=var, style="Card.TCheckbutton")
                    chk_btn.pack(anchor=tk.W, pady=2)
            elif field_type in ["select", "radio"] and options:
                var = tk.StringVar(value=str(field_value))
                field_vars[label_text] = (field_type, var)
                
                combo = ttk.Combobox(card, textvariable=var, values=options, state="readonly", font=("Segoe UI", 9))
                combo.pack(fill=tk.X, pady=2)
            elif field_type == "textarea":
                text_widget = tk.Text(card, height=3, font=("Segoe UI", 9), wrap=tk.WORD, relief=tk.SOLID, bd=1, highlightthickness=0)
                text_widget.insert(tk.END, str(field_value))
                text_widget.pack(fill=tk.X, pady=2)
                text_widget.bind("<Control-Return>", lambda e: (confirm_action(), "break")[1])
                text_widget.bind("<Shift-Return>", lambda e: (confirm_action(), "break")[1])
                field_vars[label_text] = ("textarea", text_widget)
            elif field_type == "file":
                var = tk.StringVar(value=str(field_value))
                field_vars[label_text] = ("file", var)
                
                file_frame = ttk.Frame(card, style="Card.TFrame")
                file_frame.pack(fill=tk.X, pady=2)
                
                entry = ttk.Entry(file_frame, textvariable=var, font=("Segoe UI", 9))
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
                
                def make_browse_callback(v=var):
                    from tkinter import filedialog
                    fn = filedialog.askopenfilename(
                        title="Select File",
                        filetypes=[("All Files", "*.*"), ("PDF Files", "*.pdf"), ("Word Files", "*.doc;*.docx")]
                    )
                    if fn:
                        v.set(fn)
                        
                def make_linkedin_callback(v=var):
                    v.set("__edit_on_linkedin__")
                    on_confirm()
                    
                browse_btn = ttk.Button(file_frame, text="Browse...", command=make_browse_callback, width=10)
                browse_btn.pack(side=tk.LEFT, padx=(0, 5))
                
                edit_btn = ttk.Button(file_frame, text="Edit on LinkedIn", command=make_linkedin_callback, width=15)
                edit_btn.pack(side=tk.LEFT)
            else:
                text_widget = tk.Text(card, height=2, font=("Segoe UI", 9), wrap=tk.WORD, relief=tk.SOLID, bd=1, highlightthickness=0)
                text_widget.insert(tk.END, str(field_value))
                text_widget.pack(fill=tk.X, pady=2)
                text_widget.bind("<Control-Return>", lambda e: (confirm_action(), "break")[1])
                text_widget.bind("<Shift-Return>", lambda e: (confirm_action(), "break")[1])
                field_vars[label_text] = ("text_widget", text_widget)

        # Recursively bind mousewheel to all widgets in the scrollable area
        def bind_mousewheel(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel(child)
        bind_mousewheel(scrollable_frame)

        def on_confirm():
            updated_fields = []
            for field in fields:
                lbl = field["label"]
                ftype, widget_or_var = field_vars[lbl]
                
                if ftype in ["textarea", "text_widget"]:
                    val = widget_or_var.get("1.0", tk.END).strip()
                elif ftype == "checkbox":
                    val = "Yes" if widget_or_var.get() else "No"
                elif ftype == "checklist":
                    val = [opt for opt, var in widget_or_var if var.get()]
                else:
                    val = widget_or_var.get().strip()
                
                updated_field = field.copy()
                updated_field["value"] = val
                updated_fields.append(updated_field)
            
            response["answer"] = {"fields": updated_fields}
            response["save"] = False
            root.destroy()

        def on_skip():
            response["answer"] = "__skip_job__"
            response["save"] = False
            root.destroy()

        confirm_action = on_confirm
        skip_action = on_skip

    # Handle standard window close (X button)
    def on_window_close():
        response["answer"] = None
        response["save"] = False
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_window_close)

    # Footer Buttons Layout (Frame already packed early at the bottom)

    # Button Labels
    confirm_text = payload.get("action_label") or payload.get("confirm_label") or "Confirm"
    cancel_text = payload.get("cancel_label") or ("Skip this job" if popup_type in ["question_text", "question_number", "question_select", "question_file", "question_checkbox"] else "Cancel")

    # Cancel/Skip Button
    cancel_btn = ttk.Button(button_frame, text=cancel_text, command=skip_action, style="Secondary.TButton")
    cancel_btn.pack(side=tk.LEFT, ipadx=10, ipady=4)

    # Skip Question Button
    if popup_type in ["question_text", "question_number", "question_select", "question_file", "question_checkbox"]:
        def skip_question_action():
            response["answer"] = "__skip_question__"
            response["save"] = False
            root.destroy()
        skip_q_btn = ttk.Button(button_frame, text="Skip Question", command=skip_question_action, style="Secondary.TButton")
        skip_q_btn.pack(side=tk.LEFT, padx=(10, 0), ipadx=10, ipady=4)

    # Confirm Button
    confirm_btn = ttk.Button(button_frame, text=confirm_text, command=confirm_action, style="Primary.TButton")
    confirm_btn.pack(side=tk.RIGHT, ipadx=10, ipady=4)

    # Bind Keyboard Shortcuts
    if entry_widget:
        if isinstance(entry_widget, tk.Text):
            entry_widget.bind("<Control-Return>", lambda e: (confirm_action(), "break")[1])
            entry_widget.bind("<Shift-Return>", lambda e: (confirm_action(), "break")[1])
        else:
            entry_widget.bind("<Return>", lambda e: confirm_action())
    else:
        root.bind("<Return>", lambda e: confirm_action())
    
    root.bind("<Escape>", lambda e: skip_action())

    def on_close_window():
        response["answer"] = "__close_popup__"
        response["save"] = False
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close_window)

    # Start Tkinter event loop (blocks until root.destroy() is called)
    root.mainloop()

    return response["answer"], response["save"]

if __name__ == "__main__":
    import sys
    import json
    try:
        # Read JSON from stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.exit(1)
        payload = json.loads(input_data)
        answer, save = show_desktop_popup(payload)
        # Output result as JSON to stdout
        print(json.dumps({"answer": answer, "save": save}))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
