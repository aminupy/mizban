import tkinter as tk
import io
import sys
import os
import webbrowser
import mizban
from tkinter import scrolledtext
from tkinter import font as tkfont

def start_gui():
    url = mizban.get_server_url()

    # Capture the ASCII QR code output
    qr_output = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = qr_output
    mizban.print_qr_code(url)
    sys.stdout = original_stdout
    qr_ascii = qr_output.getvalue()

    # GUI setup
    root = tk.Tk()
    root.title("🚀 Mizban LAN Server Info")
    root.geometry("600x500")

    title_font = tkfont.Font(family="Helvetica", size=16, weight="bold")
    label_font = tkfont.Font(family="Helvetica", size=12)

    tk.Label(root, text="🚀  Mizban — LAN File Sharing Server", font=title_font).pack(pady=10)

    # Shared folder label (clickable)
    folder_label = tk.Label(
        root,
        text=f"📂  Shared folder : {mizban.UPLOAD_DIR}",
        font=label_font,
        fg="blue",
        cursor="hand2",
        wraplength=550,
        justify="left"
    )
    folder_label.pack(pady=5)
    folder_label.bind("<Button-1>", lambda e: open_folder(mizban.UPLOAD_DIR))

    # URL label (clickable)
    url_label = tk.Label(
        root,
        text=f"🌐 Access URL: {url}",
        font=label_font,
        fg="blue",
        cursor="hand2"
    )
    url_label.pack(pady=5)
    url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

    # QR Code output (centered)
    tk.Label(root, text="📱QR code : Scan below to open in your mobile browser", font=label_font).pack(pady=5)

    qr_frame_container = tk.Frame(root)
    qr_frame_container.pack(fill="both", expand=True)

    qr_frame = tk.Frame(qr_frame_container)
    qr_frame.place(relx=0.5, rely=0.5, anchor="center")  # center the frame

    qr_box = scrolledtext.ScrolledText(qr_frame, width=60, height=20, font=("Courier", 10))
    qr_box.insert(tk.END, qr_ascii)
    qr_box.configure(state="disabled")
    qr_box.pack()

    # Handle close window
    def on_close():
        print("[INFO] Closing Mizban...")
        root.destroy()
        os._exit(0)  # force kill the whole process

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()

def open_folder(path):
    if sys.platform.startswith('linux'):
        os.system(f'xdg-open "{path}"')
    elif sys.platform == "darwin":  # macOS
        os.system(f'open "{path}"')
    elif sys.platform == "win32":
        os.startfile(path)
