from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import io
import sys
import os
import webbrowser

from core import utils, server
from config import settings


def start_gui():
    url = utils.get_server_url(settings.PORT)

    # Capture the ASCII QR code output
    qr_output = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = qr_output
    utils.print_qr_code(url)
    sys.stdout = original_stdout
    qr_ascii = qr_output.getvalue()

    # GUI setup
    root = tk.Tk()
    root.title("Mizban")
    root.geometry("600x500")

    icon_path = Path(f"{Path().resolve()}/clients/frontend/favicon.ico")
    if sys.platform == "win32" and icon_path.exists():
        root.iconbitmap(str(icon_path))

    style = ttk.Style()
    style.configure("Title.TLabel", font=("Helvetica", 16, "bold"))
    style.configure("Body.TLabel", font=("Helvetica", 12))
    style.configure("Mono.TLabel", font=("Courier", 10))

    ttk.Label(root, text="🚀  Mizban — LAN File Sharing Server", style="Title.TLabel").pack(pady=20)

    # Folder Label
    folder_label_var = tk.StringVar()
    folder_label_var.set(f"📂  Shared folder : {settings.MIZBAN_SHARED_DIR}")

    folder_label = ttk.Label(
        root,
        textvariable=folder_label_var,
        style="Body.TLabel",
        foreground="blue",
        cursor="hand2",
        wraplength=550,
        justify="left"
    )
    folder_label.pack(pady=5)
    folder_label.bind("<Button-1>", lambda e: open_folder(settings.MIZBAN_SHARED_DIR))

    # URL Label
    url_label = ttk.Label(
        root,
        text=f"🌐 Access URL: {url}",
        style="Body.TLabel",
        foreground="blue",
        cursor="hand2"
    )
    url_label.pack(pady=5)
    url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

    # Folder selection Button
    def choose_folder():
        shared_folder = filedialog.askdirectory(title="Select Shared Folder")
        if shared_folder:
            settings.MIZBAN_SHARED_DIR = shared_folder
            settings.save()
            folder_label_var.set(f"📂  Shared folder : {settings.MIZBAN_SHARED_DIR}")

    folder_button = ttk.Button(root, text="Select Shared Folder", command=choose_folder)
    folder_button.pack(pady=10)

    # QR code display
    ttk.Label(
        root,
        text="📱 QR code : Scan below to open in your mobile browser",
        style="Body.TLabel"
    ).pack(pady=(30, 10))

    qr_frame = ttk.Frame(root)
    qr_frame.pack(fill="x", padx=10, pady=10)

    qr_label = ttk.Label(
        qr_frame,
        text=qr_ascii,
        style="Mono.TLabel",
        justify="center"
    )
    qr_label.pack(anchor="center")


    def on_close():
        print("[INFO] Closing Mizban...")
        root.destroy()
        os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


def open_folder(path):
    if sys.platform.startswith('linux'):
        os.system(f'xdg-open "{path}"')
    elif sys.platform == "darwin":  # macOS
        os.system(f'open "{path}"')
    elif sys.platform == "win32":
        os.startfile(path)


if __name__ == "__main__":
    threading.Thread(target=start_gui, daemon=True).start()
    server.start_server()
