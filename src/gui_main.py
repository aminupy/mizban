from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont
import sys
import os
import webbrowser

from core import utils, server
from config import settings
from ui_utils import RoundedFrame, create_gradient_title

print(settings.FRONTEND_DIR)
class MizbanApp:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.create_styles()
        self.create_widgets()
        self.connect_commands()
        
        # Adjust window width once at startup
        self.root.after(100, self.adjust_window_width)

    def setup_window(self):
        """Configures the main root window."""
        self.root.title("Mizban")
        self.root.geometry("650x600")
        self.root.configure(bg="#f0f0f0")

        icon_path = Path(f"{settings.FRONTEND_DIR}/favicon.ico")
        if sys.platform == "win32" and icon_path.exists():
            self.root.iconbitmap(str(icon_path))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_styles(self):
        """Sets up fonts and ttk styles."""
        self.default_font_name = "Trebuchet MS"
        self.static_font_size = 11
        style = ttk.Style()
        style.configure("TButton", font=(self.default_font_name, 10))

    def create_widgets(self):
        """Creates and lays out all the widgets in the UI."""
        # --- Main Frame ---
        self.main_frame = tk.Frame(self.root, bg="#f0f0f0", padx=20, pady=20)
        self.main_frame.pack(expand=True, fill="both")
        self.main_frame.rowconfigure(3, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        
        # --- Title ---
        gradient_title = create_gradient_title(
            parent=self.main_frame, bold_text="Mizban", regular_text=" — LAN File Sharing Server",
            font_name=self.default_font_name, font_size=18, start_color="blue", end_color="purple"
        )
        gradient_title.grid(row=0, column=0, pady=(0, 30))

        # --- Card 1: Shared Folder ---
        folder_card = RoundedFrame(self.main_frame, radius=15, padding=15)
        folder_card.grid(row=1, column=0, pady=5, sticky="ew")
        folder_content_frame = folder_card.inner_frame
        folder_content_frame.columnconfigure(1, weight=1)

        self.bold_folder_label = tk.Label(folder_content_frame, text="📂  Shared folder: ", font=(self.default_font_name, self.static_font_size, "bold"), bg="white")
        self.bold_folder_label.grid(row=0, column=0, sticky="w")

        self.folder_path_var = tk.StringVar(value=f"{settings.MIZBAN_SHARED_DIR}")
        self.folder_path_label = tk.Label(folder_content_frame, textvariable=self.folder_path_var, font=(self.default_font_name, self.static_font_size), fg="blue", bg="white", cursor="hand2")
        self.folder_path_label.grid(row=0, column=1, sticky="w")

        self.folder_button = ttk.Button(folder_content_frame, text="Change Folder", padding=2)
        self.folder_button.grid(row=0, column=2, padx=(10,0))
        folder_card.fit_to_content()

        # --- Card 2: Access URL ---
        url_card = RoundedFrame(self.main_frame, radius=15, padding=15)
        url_card.grid(row=2, column=0, pady=5, sticky="ew")
        url_content_frame = url_card.inner_frame
        
        self.url = utils.get_server_url(settings.PORT)
        tk.Label(url_content_frame, text="🌐 Access URL: ", font=(self.default_font_name, self.static_font_size, "bold"), bg="white").pack(side=tk.LEFT)
        self.url_label = tk.Label(url_content_frame, text=self.url, font=(self.default_font_name, self.static_font_size), fg="blue", bg="white", cursor="hand2")
        self.url_label.pack(side=tk.LEFT)
        url_card.fit_to_content()
        
        # --- Card 3: QR Code ---
        qr_card = RoundedFrame(self.main_frame, radius=15, padding=15)
        qr_card.grid(row=3, column=0, pady=(25, 0), sticky="nsew")
        qr_content_frame = qr_card.inner_frame
        
        qr_text_frame = tk.Frame(qr_content_frame, bg="white")
        qr_text_frame.pack(anchor="center", pady=(0, 10))
        tk.Label(qr_text_frame, text="📱 QR code:", font=(self.default_font_name, self.static_font_size, "bold"), bg="white").pack(side=tk.LEFT)
        tk.Label(qr_text_frame, text=" Scan below to open in your mobile browser", font=(self.default_font_name, self.static_font_size), bg="white").pack(side=tk.LEFT)
        
        qr_ascii = utils.generate_qr_ascii(self.url)
        tk.Label(qr_content_frame, text=qr_ascii, font=("Courier", 10), bg="white", justify="center").pack(expand=True, fill="both")

    def connect_commands(self):
        """Binds all commands and events to their functions."""
        self.folder_path_label.bind("<Button-1>", lambda e: utils.open_folder(settings.MIZBAN_SHARED_DIR))
        self.url_label.bind("<Button-1>", lambda e: webbrowser.open(self.url))
        self.folder_button.configure(command=self.choose_folder)

    def choose_folder(self):
        """Handles the 'Change Folder' button command."""
        shared_folder = filedialog.askdirectory(title="Select Shared Folder")
        if shared_folder:
            settings.MIZBAN_SHARED_DIR = shared_folder
            settings.save()
            self.folder_path_var.set(f"{settings.MIZBAN_SHARED_DIR}")
            self.adjust_window_width()

    def adjust_window_width(self):
        """Calculates required width and resizes the window."""
        try:
            if not self.root.winfo_exists(): return
        except tk.TclError:
            return
        self.root.update_idletasks()
        
        bold_label_width = self.bold_folder_label.winfo_width()
        path_font = tkfont.Font(font=self.folder_path_label.cget("font"))
        path_label_width = path_font.measure(self.folder_path_var.get())
        button_width = self.folder_button.winfo_width()
        
        required_content_width = bold_label_width + path_label_width + button_width + 100
        current_height = self.root.winfo_height()
        self.root.minsize(width=required_content_width, height=current_height)

        if self.root.winfo_width() < required_content_width:
            self.root.geometry(f"{required_content_width}x{current_height}")

    def on_close(self):
        """Handles the window closing event."""
        print("[INFO] Closing Mizban...")
        self.root.destroy()
        os._exit(0)


def start_gui():
    root = tk.Tk()
    app = MizbanApp(root)
    root.mainloop()


if __name__ == "__main__":
    threading.Thread(target=start_gui, daemon=True).start()
    server.start_server()
