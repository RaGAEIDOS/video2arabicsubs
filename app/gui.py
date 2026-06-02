import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from app import __app_name__, __version__
from app.processor import Processor

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pystray
    from pystray import MenuItem as TrayItem
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

VIDEO_EXTENSIONS = (
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
    ".mpg", ".mpeg", ".m4v", ".3gp", ".ts", ".mts", ".vob",
    ".ogg", ".ogv", ".mxf", ".mpv", ".asf",
)

COLOR_PRIMARY = "#1a73e8"
COLOR_SUCCESS = "#0f9d58"
COLOR_ERROR = "#ea4335"
COLOR_BG = "#f8f9fa"
COLOR_DARK = "#202124"


class App:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{__app_name__} v{__version__}")
        self.root.geometry("780x700")
        self.root.minsize(650, 600)
        self.root.configure(bg=COLOR_BG)

        self.video_files = []
        self.video_status = {}
        self.processor = Processor()
        self.thread = None
        self.tray_icon = None
        self.tray_image = None

        self._setup_style()
        self._build_header()
        self._build_body()
        self._setup_tray()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Style ──────────────────────────────────────────────
    def _setup_style(self):
        style = ttk.Style()
        available = style.theme_names()
        for t in ("clam", "vista", "winnative", "default"):
            if t in available:
                style.theme_use(t)
                break

        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"),
                        foreground=COLOR_DARK, background=COLOR_BG)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 9),
                        foreground="#5f6368", background=COLOR_BG)
        style.configure("Header.TFrame", background=COLOR_BG)
        style.configure("Card.TLabelframe", background=COLOR_BG,
                        relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Success.TLabel", foreground=COLOR_SUCCESS,
                        font=("Segoe UI", 10))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TFrame", background=COLOR_BG)
        style.configure("TLabel", background=COLOR_BG)

    # ── Header with logo ───────────────────────────────────
    def _build_header(self):
        header = ttk.Frame(self.root, style="Header.TFrame")
        header.pack(fill=tk.X, padx=15, pady=(15, 5))

        self.logo_img = None
        logo_path = Path("img") / "first-logo-design.png"
        if logo_path.exists() and HAS_PIL:
            try:
                img = Image.open(logo_path).resize((64, 64),
                                                   Image.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                lbl_logo = tk.Label(header, image=self.logo_img,
                                    bg=COLOR_BG, cursor="hand2")
                lbl_logo.pack(side=tk.LEFT, padx=(0, 12))
            except Exception:
                pass

        text_frame = ttk.Frame(header, style="Header.TFrame")
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(text_frame, text=__app_name__,
                  style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(text_frame,
                  text=f"{__version__} — تحويل الفيديو إلى ترجمة عربية",
                  style="Subtitle.TLabel").pack(anchor=tk.W)

    # ── Body ───────────────────────────────────────────────
    def _build_body(self):
        body = ttk.Frame(self.root)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self._build_file_section(body)
        self._build_output_section(body)
        self._build_model_section(body)
        self._build_action_section(body)
        self._build_progress_section(body)
        self._build_status_section(body)

    # ── File selection ─────────────────────────────────────
    def _build_file_section(self, parent):
        frame = ttk.LabelFrame(parent, text="اختيار الفيديوهات",
                               style="Card.TLabelframe", padding=10)
        frame.pack(fill=tk.X, pady=(0, 8))

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(btn_row, text="📁  اختيار فيديوهات",
                   command=self._select_files).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="📂  اختيار مجلد",
                   command=self._select_folder).pack(side=tk.LEFT)

        list_row = ttk.Frame(frame)
        list_row.pack(fill=tk.X)

        list_col = ttk.Frame(list_row)
        list_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_col, orient=tk.VERTICAL)
        self.files_listbox = tk.Listbox(list_col, height=6,
                                        yscrollcommand=scrollbar.set,
                                        relief="solid", borderwidth=1,
                                        font=("Segoe UI", 9))
        scrollbar.config(command=self.files_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btn_col = ttk.Frame(list_row)
        btn_col.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(btn_col, text="▲", width=3,
                   command=self._move_up).pack(pady=(0, 2))
        ttk.Button(btn_col, text="▼", width=3,
                   command=self._move_down).pack(pady=(0, 6))
        ttk.Button(btn_col, text="✕", width=3,
                   command=self._remove_selected).pack()

    def _select_files(self):
        files = filedialog.askopenfilenames(
            title="اختيار ملفات فيديو",
            filetypes=[("Video files", " ".join(
                f"*{e}" for e in VIDEO_EXTENSIONS))],
        )
        for path in files:
            if path not in self.video_files:
                self.video_files.append(path)
                self.video_status[path] = "pending"
        self._refresh_listbox()

    def _select_folder(self):
        folder = filedialog.askdirectory(title="اختيار مجلد فيديوهات")
        if folder:
            added = 0
            for f in os.listdir(folder):
                if f.lower().endswith(VIDEO_EXTENSIONS):
                    path = os.path.join(folder, f)
                    if path not in self.video_files:
                        self.video_files.append(path)
                        self.video_status[path] = "pending"
                        added += 1
            if added > 0:
                self._refresh_listbox()

    def _remove_selected(self):
        sel = self.files_listbox.curselection()
        for i in reversed(sel):
            path = self.video_files.pop(i)
            self.video_status.pop(path, None)
        self._refresh_listbox()

    def _move_up(self):
        sel = self.files_listbox.curselection()
        if sel and sel[0] > 0:
            i = sel[0]
            self.video_files[i], self.video_files[i - 1] = \
                self.video_files[i - 1], self.video_files[i]
            self._refresh_listbox()
            self.files_listbox.selection_set(i - 1)

    def _move_down(self):
        sel = self.files_listbox.curselection()
        if sel and sel[0] < len(self.video_files) - 1:
            i = sel[0]
            self.video_files[i], self.video_files[i + 1] = \
                self.video_files[i + 1], self.video_files[i]
            self._refresh_listbox()
            self.files_listbox.selection_set(i + 1)

    def _refresh_listbox(self):
        self.files_listbox.delete(0, tk.END)
        for path in self.video_files:
            name = os.path.basename(path)
            status = self.video_status.get(path, "pending")
            if status == "done":
                name = f"✔ {name}"
            elif status == "error":
                name = f"✘ {name}"
            self.files_listbox.insert(tk.END, name)

    # ── Output path ────────────────────────────────────────
    def _build_output_section(self, parent):
        frame = ttk.LabelFrame(parent, text="مسار الحفظ",
                               style="Card.TLabelframe", padding=10)
        frame.pack(fill=tk.X, pady=(0, 8))

        self.output_path = tk.StringVar(value=str(Path.cwd()))
        entry = ttk.Entry(frame, textvariable=self.output_path,
                          font=("Segoe UI", 9))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(frame, text="📂  تصفح",
                   command=self._select_output).pack(side=tk.RIGHT)

    def _select_output(self):
        folder = filedialog.askdirectory(title="اختيار مجلد للحفظ")
        if folder:
            self.output_path.set(folder)

    # ── Model selection ────────────────────────────────────
    def _build_model_section(self, parent):
        frame = ttk.LabelFrame(parent, text="نموذج Whisper",
                               style="Card.TLabelframe", padding=10)
        frame.pack(fill=tk.X, pady=(0, 8))

        self.model_size = tk.StringVar(value="small")
        row = ttk.Frame(frame)
        row.pack()
        ttk.Radiobutton(row, text="Tiny (أسرع)",
                        variable=self.model_size,
                        value="tiny").pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(row, text="Base",
                        variable=self.model_size,
                        value="base").pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(row, text="Small (موصى به)",
                        variable=self.model_size,
                        value="small").pack(side=tk.LEFT, padx=8)

    # ── Action buttons ─────────────────────────────────────
    def _build_action_section(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(0, 8))

        self.start_btn = ttk.Button(
            frame, text="▶  ابدأ الترجمة",
            command=self._start_processing,
            style="Primary.TButton",
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.stop_btn = ttk.Button(
            frame, text="⏹  إيقاف",
            command=self._stop_processing,
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.exit_btn = ttk.Button(
            frame, text="✕  خروج",
            command=self._exit_app,
        )
        self.exit_btn.pack(side=tk.RIGHT)

    # ── Progress ───────────────────────────────────────────
    def _build_progress_section(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(0, 8))

        self.progress = ttk.Progressbar(frame, mode="determinate",
                                        value=0)
        self.progress.pack(fill=tk.X, expand=True, side=tk.LEFT)

        self.progress_label = ttk.Label(frame, text="0%",
                                        width=5, anchor=tk.E)
        self.progress_label.pack(side=tk.LEFT, padx=(6, 0))

    # ── Status log ─────────────────────────────────────────
    def _build_status_section(self, parent):
        frame = ttk.LabelFrame(parent, text="سجل التشغيل",
                               style="Card.TLabelframe", padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self.status_text = tk.Text(frame, height=8, wrap=tk.WORD,
                                   state=tk.DISABLED,
                                   relief="solid", borderwidth=1,
                                   font=("Consolas", 9),
                                   bg="#1e1e1e", fg="#d4d4d4",
                                   insertbackground="white")
        self.status_text.pack(fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(self.status_text, orient=tk.VERTICAL,
                               command=self.status_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.config(yscrollcommand=scroll.set)

    # ── System tray ────────────────────────────────────────
    def _setup_tray(self):
        if not HAS_TRAY:
            return
        try:
            img_path = Path("img") / "first-logo-design.png"
            if img_path.exists() and HAS_PIL:
                tray_img = Image.open(img_path).resize((64, 64),
                                                       Image.LANCZOS)
            else:
                tray_img = Image.new("RGB", (64, 64), COLOR_PRIMARY)

            def show_window(icon, item):
                self.root.after(0, self._show_window)

            def quit_app(icon, item):
                self.root.after(0, self._exit_app)

            menu = (
                TrayItem("🪟  إظهار النافذة", show_window, default=True),
                TrayItem("✕  خروج", quit_app),
            )
            self.tray_icon = pystray.Icon(
                __app_name__, tray_img,
                f"{__app_name__} v{__version__}", menu)
            threading.Thread(target=self.tray_icon.run,
                             daemon=True).start()
        except Exception:
            self.tray_icon = None

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_close(self):
        if self.tray_icon:
            self.root.withdraw()
        else:
            self._exit_app()

    def _exit_app(self):
        try:
            if self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()
        os._exit(0)

    # ── Logging (thread-safe) ──────────────────────────────
    def _log(self, message):
        self.root.after(0, self._do_log, message)

    def _do_log(self, message):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def _update_progress(self, value):
        self.root.after(0, self._do_update_progress, value)

    def _do_update_progress(self, value):
        self.progress["value"] = value
        self.progress_label.config(text=f"{int(value)}%")

    def _update_item_status(self, path, status):
        self.root.after(0, self._do_update_item_status, path, status)

    def _do_update_item_status(self, path, status):
        if path in self.video_status:
            self.video_status[path] = status
        self._refresh_listbox()

    # ── Processing ─────────────────────────────────────────
    def _start_processing(self):
        if not self.video_files:
            messagebox.showwarning("تحذير",
                                   "يرجى اختيار فيديو واحد على الأقل.")
            return

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.exit_btn.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self.progress_label.config(text="0%")

        self._log(f"بدء معالجة {len(self.video_files)} فيديو...")
        self._log("─" * 40)

        for path in self.video_files:
            self.video_status[path] = "pending"
        self._refresh_listbox()

        self.thread = threading.Thread(target=self._process,
                                       daemon=True)
        self.thread.start()

    def _process(self):
        try:
            self.processor.process(
                video_paths=self.video_files,
                output_dir=self.output_path.get(),
                model_size=self.model_size.get(),
                progress_callback=self._update_progress,
                status_callback=self._log,
                item_callback=self._update_item_status,
            )
        except Exception as e:
            import traceback
            self._log(f"❌ خطأ غير متوقع: {e}")
            self._log(traceback.format_exc())
        finally:
            self.root.after(0, self._reset_ui)

    def _reset_ui(self):
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.exit_btn.config(state=tk.NORMAL)

    def _stop_processing(self):
        self.processor.cancel()
        self._log("⏹ جاري إيقاف المعالجة...")
        self.stop_btn.config(state=tk.DISABLED)

    def run(self):
        self.root.mainloop()
