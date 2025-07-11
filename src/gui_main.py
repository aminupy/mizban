from pathlib import Path
import threading
import tkinter as tk
from tkinter import font as tkfont
import io
import sys
import os
import webbrowser
import core

def start_gui():
    url = core.get_server_url()

    # Capture the ASCII QR code output
    qr_output = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = qr_output
    core.print_qr_code(url)
    sys.stdout = original_stdout
    qr_ascii = qr_output.getvalue()

    # GUI setup
    root = tk.Tk()
    root.title("Mizban")
    root.geometry("600x500")
    
    icon_path = f"{Path().resolve()}/favicon.ico"
    print(icon_path)
    # if icon_path.exists():
    root.iconbitmap(str(icon_path))
    # else:
    #     print(f"[WARN] Icon not found at: {icon_path}")

    title_font = tkfont.Font(family="Helvetica", size=16, weight="bold")
    label_font = tkfont.Font(family="Helvetica", size=12)
    mono_font = tkfont.Font(family="Courier", size=10)

    tk.Label(root, text="🚀  Mizban — LAN File Sharing Server", font=title_font).pack(pady=20)

    folder_label = tk.Label(
        root,
        text=f"📂  Shared folder : {core.UPLOAD_DIR}",
        font=label_font,
        fg="blue",
        cursor="hand2",
        wraplength=550,
        justify="left"
    )
    folder_label.pack(pady=5)
    folder_label.bind("<Button-1>", lambda e: open_folder(core.UPLOAD_DIR))

    url_label = tk.Label(
        root,
        text=f"🌐 Access URL: {url}",
        font=label_font,
        fg="blue",
        cursor="hand2"
    )
    url_label.pack(pady=5)
    url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

    tk.Label(root, text="📱 QR code : Scan below to open in your mobile browser", font=label_font).pack(pady=(30, 0))
    # QR code frame centered
    qr_frame = tk.Frame(root)
    qr_frame.pack(fill="both", expand=True)

    qr_label = tk.Label(qr_frame, text=qr_ascii, font=mono_font, justify="center")
    qr_label.place(relx=0.5, rely=0.5, anchor="center")

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
    core.start_server()