from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import webbrowser
from contextlib import suppress
from pathlib import Path

from config import settings
from core import server, utils

try:
    import tkinter as tk
    from tkinter import filedialog, font as tkfont, ttk
except Exception as exc:  # pragma: no cover - depends on host environment
    tk = None
    filedialog = None
    tkfont = None
    ttk = None
    _TK_IMPORT_ERROR = exc
else:
    _TK_IMPORT_ERROR = None

pystray = None
Image = None
_PYSTRAY_IMPORT_ERROR: Exception | None = None
_PIL_IMPORT_ERROR: Exception | None = None

def _ensure_tray_dependencies() -> bool:
    global pystray, Image, _PYSTRAY_IMPORT_ERROR, _PIL_IMPORT_ERROR
    if pystray is None and _PYSTRAY_IMPORT_ERROR is None:
        try:
            import pystray as _pystray
        except Exception as exc:  # pragma: no cover - depends on host environment
            _PYSTRAY_IMPORT_ERROR = exc
            pystray = None
        else:
            pystray = _pystray
    if Image is None and _PIL_IMPORT_ERROR is None:
        try:
            from PIL import Image as _Image
        except Exception as exc:  # pragma: no cover - depends on Pillow availability
            _PIL_IMPORT_ERROR = exc
            Image = None
        else:
            Image = _Image
    return pystray is not None and Image is not None

from ui_utils import RoundedFrame, create_gradient_title


logger = logging.getLogger("mizban.gui")


def _gui_available() -> tuple[bool, str | None]:
    if tk is None:
        return False, f"tkinter import failed: {_TK_IMPORT_ERROR}"
    if sys.platform.startswith("linux"):
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False, "No DISPLAY/WAYLAND_DISPLAY environment variable set."
    return True, None


def _launch_cli(reason: str) -> None:
    logger.info("Falling back to CLI mode (%s).", reason)
    # Import lazily to avoid circular imports when running the GUI normally.
    from cli_main import run as cli_run

    cli_run()


def _show_dialog(title: str, message: str, kind: str = "info") -> None:
    if tk is None:
        logger.info("%s: %s", title, message)
        print(f"{title}: {message}")
        return

    dummy_root: tk.Tk | None = None
    try:
        from tkinter import messagebox

        dummy_root = tk.Tk()
        dummy_root.withdraw()
        if kind == "error":
            messagebox.showerror(title, message, parent=dummy_root)
        else:
            messagebox.showinfo(title, message, parent=dummy_root)
    except Exception as exc:  # pragma: no cover - GUI environment specific
        logger.warning("Unable to display %s dialog: %s", kind, exc)
        print(f"{title}: {message}")
    finally:
        if dummy_root is not None:
            dummy_root.destroy()


if getattr(sys, "frozen", False) or "__compiled__" in globals():
    log_file_path = Path.home() / ".config" / "Mizban" / "logs.txt"
    try:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = open(log_file_path, "a", buffering=1)
        sys.stderr = sys.stdout
    except Exception as exc:  # pragma: no cover - depends on filesystem
        logger.warning("Unable to redirect stdout/stderr to %s: %s", log_file_path, exc)


class MizbanApp:
    def __init__(self, root, http_server, server_thread):
        self.root = root
        self.http_server = http_server
        self.server_thread = server_thread
        self.server_port = http_server.server_address[1]
        self.icon = None
        self._tray_thread = None
        self.setup_window()
        self.create_styles()
        self.create_widgets()
        self.connect_commands()

        self.setup_tray_icon()
        
        # Adjust window width once at startup
        self.root.after(100, self.adjust_window_width)

    def setup_tray_icon(self):
        """Creates and runs the system tray icon in a separate thread."""
        if not _ensure_tray_dependencies():
            if _PYSTRAY_IMPORT_ERROR:
                logger.info(
                    "System tray integration is unavailable: %s", _PYSTRAY_IMPORT_ERROR
                )
            if _PIL_IMPORT_ERROR:
                logger.info(
                    "Tray icon support requires Pillow; skipping system tray integration."
                )
            return
        # Load the icon image
        # Assuming your icon is in the project root, accessible via BASE_DIR
        icon_path = settings.BASE_DIR / "clients" / "frontend" / "favicon.ico"
        try:
            image = Image.open(icon_path)
        except FileNotFoundError:
            logger.warning("Tray icon not found at %s; skipping system tray integration.", icon_path)
            return
        except Exception as exc:
            logger.warning("Unable to load tray icon from %s: %s", icon_path, exc)
            return

        menu = (
            pystray.MenuItem('Show', self.show_window, default=True),
            pystray.MenuItem('Quit', self.quit_window)
        )

        try:
            self.icon = pystray.Icon("mizban", image, "Mizban File Server", menu)
        except Exception as exc:  # pragma: no cover - environment specific
            logger.warning("Unable to initialise system tray icon: %s", exc)
            self.icon = None
            return

        def run_icon():
            try:
                self.icon.run()
            except Exception as exc:  # pragma: no cover - environment specific
                logger.warning("System tray icon stopped unexpectedly: %s", exc)

        self._tray_thread = threading.Thread(target=run_icon, daemon=True)
        self._tray_thread.start()
    
    def hide_window(self):
        """Hides the main window."""
        self.root.withdraw()
        title = "Mizban is Running"
        message = "Mizban is still running in the system tray."
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception as exc:  # pragma: no cover - environment specific
                logger.debug("Tray notification failed: %s", exc)

    def show_window(self):
        """Shows the main window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit_window(self):
        """Stops the tray icon and schedules the application to quit."""
        # First, stop the tray icon's own loop
        if self.icon:
            try:
                self.icon.stop()
            except Exception as exc:  # pragma: no cover - environment specific
                logger.debug("Tray icon stop failed: %s", exc)
        
        # ✨ Ask the main GUI thread to run the shutdown command safely
        self.root.after(100, self._shutdown)

    def _shutdown(self):
        """Destroys the root window, causing the mainloop and app to exit."""
        if self.icon:
            with suppress(Exception):
                self.icon.visible = False
        if self.http_server:
            try:
                self.http_server.shutdown()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Error shutting down server: %s", exc)
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
        if self.http_server:
            with suppress(Exception):
                self.http_server.server_close()
        self.http_server = None
        self.server_thread = None
        self.root.destroy()


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
        
        self.url = utils.get_server_url(self.server_port)
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
        if filedialog is None:
            _show_dialog("Mizban", "Folder selection is not available.", kind="error")
            return
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
        self.hide_window()


def start_gui(http_server):
    if tk is None:
        raise RuntimeError("Tkinter is not available.")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError(f"Tkinter failed to initialise: {exc}") from exc
    server_thread = threading.Thread(
        target=server.serve_forever,
        args=(http_server,),
        daemon=True,
        name="mizban-http-server",
    )
    server_thread.start()

    app = MizbanApp(root, http_server, server_thread)
    try:
        root.mainloop()
    finally:
        if app.http_server:
            with suppress(Exception):
                app.http_server.shutdown()
            with suppress(Exception):
                app.http_server.server_close()
        if server_thread.is_alive():
            server_thread.join(timeout=5)
    return app


def main() -> None:
    gui_ok, reason = _gui_available()
    if not gui_ok:
        _launch_cli(reason or "GUI not available")
        return

    app_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with suppress(OSError):
        app_lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        app_lock_socket.bind(("127.0.0.1", 60123))
        app_lock_socket.listen(1)
    except OSError as err:
        logger.info("Mizban appears to be running already: %s", err)
        _show_dialog(
            "Mizban", "Mizban is already running.\n\nPlease check your system tray."
        )
        with suppress(Exception):
            app_lock_socket.close()
        sys.exit(0)

    http_server = None
    fallback_reason: str | None = None
    try:
        http_server = server.create_server()
    except OSError as exc:
        _show_dialog(
            "Mizban",
            f"Unable to start the server on {settings.HOST}:{settings.PORT}.\n\n{exc}",
            kind="error",
        )
        with suppress(Exception):
            app_lock_socket.close()
        sys.exit(1)

    try:
        start_gui(http_server)
    except RuntimeError as exc:  # pragma: no cover - environment specific
        logger.warning("GUI unavailable: %s", exc)
        fallback_reason = str(exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected Mizban GUI failure: %s", exc)
        _show_dialog("Mizban", f"Unexpected error: {exc}", kind="error")
        sys.exit(1)
    finally:
        if http_server:
            with suppress(Exception):
                http_server.shutdown()
            with suppress(Exception):
                http_server.server_close()
        with suppress(Exception):
            app_lock_socket.close()

    if fallback_reason:
        _launch_cli(fallback_reason)


if __name__ == "__main__":
    main()
