from __future__ import annotations

try:
    import tkinter as tk
except Exception as exc:  # pragma: no cover - depends on host environment
    tk = None
    _TK_IMPORT_ERROR = exc
else:
    _TK_IMPORT_ERROR = None


def _require_tk() -> None:
    if tk is None:
        raise RuntimeError(
            "Tkinter is not available in this environment. "
            "GUI components cannot be created."
        )


def create_gradient_title(
    parent,
    bold_text,
    regular_text,
    font_name,
    font_size,
    start_color,
    end_color,
):
    """
    Creates a gradient title with a bold part and a regular part.
    """
    _require_tk()
    start_r, start_g, start_b = parent.winfo_rgb(start_color)
    end_r, end_g, end_b = parent.winfo_rgb(end_color)

    title_frame = tk.Frame(parent, bg=parent.cget("bg"))

    full_text = bold_text + regular_text
    num_chars = len(full_text)
    if num_chars == 0:
        return title_frame

    font_bold = (font_name, font_size, "bold")
    font_regular = (font_name, font_size, "normal")

    for i, char in enumerate(full_text):
        # Calculate the interpolated color based on character position
        fraction = i / (num_chars - 1) if num_chars > 1 else 0
        r = int(start_r + (end_r - start_r) * fraction)
        g = int(start_g + (end_g - start_g) * fraction)
        b = int(start_b + (end_b - start_b) * fraction)

        hex_color = f"#{r>>8:02x}{g>>8:02x}{b>>8:02x}"

        # Use a bold font for the first part, regular for the second
        current_font = font_bold if i < len(bold_text) else font_regular

        char_label = tk.Label(
            title_frame,
            text=char,
            font=current_font,
            fg=hex_color,
            bg=parent.cget("bg"),
        )
        char_label.pack(side=tk.LEFT, padx=0, pady=0)

    return title_frame


if tk is not None:

    class RoundedFrame(tk.Canvas):
        """
        A custom canvas widget that draws a perfect rounded rectangle background
        and places a content frame on top.
        """

        def __init__(
            self,
            parent,
            radius=20,
            padding=10,
            bg_color="#f0f0f0",
            fg_color="white",
            **kwargs,
        ):
            super().__init__(parent, highlightthickness=0, bg=bg_color, **kwargs)
            self.radius = radius
            self.padding = padding
            self.fg_color = fg_color

            self.inner_frame = tk.Frame(self, bg=fg_color)
            self.window_id = self.create_window(
                padding, padding, window=self.inner_frame, anchor="nw"
            )

            self.bind("<Configure>", self._resize_and_redraw)

        def _resize_and_redraw(self, event):
            canvas_width = self.winfo_width()
            canvas_height = self.winfo_height()
            self.itemconfig(
                self.window_id,
                width=canvas_width - 2 * self.padding,
                height=canvas_height - 2 * self.padding,
            )
            self._draw_perfect_rounded_rect(canvas_width, canvas_height)

        def _draw_perfect_rounded_rect(self, width, height):
            self.delete("shape")
            radius = min(self.radius, width / 2, height / 2)

            if radius < 1:
                self.create_rectangle(
                    0,
                    0,
                    width,
                    height,
                    fill=self.fg_color,
                    outline="",
                    tags="shape",
                )
                return

            # Draw the four corner arcs
            self.create_arc(
                0,
                0,
                2 * radius,
                2 * radius,
                start=90,
                extent=90,
                fill=self.fg_color,
                outline="",
                tags="shape",
            )
            self.create_arc(
                width - 2 * radius,
                0,
                width,
                2 * radius,
                start=0,
                extent=90,
                fill=self.fg_color,
                outline="",
                tags="shape",
            )
            self.create_arc(
                0,
                height - 2 * radius,
                2 * radius,
                height,
                start=180,
                extent=90,
                fill=self.fg_color,
                outline="",
                tags="shape",
            )
            self.create_arc(
                width - 2 * radius,
                height - 2 * radius,
                width,
                height,
                start=270,
                extent=90,
                fill=self.fg_color,
                outline="",
                tags="shape",
            )

            # Draw the four connecting rectangles (sides)
            self.create_rectangle(
                radius,
                0,
                width - radius,
                height,
                fill=self.fg_color,
                outline="",
                tags="shape",
            )
            self.create_rectangle(
                0,
                radius,
                width,
                height - radius,
                fill=self.fg_color,
                outline="",
                tags="shape",
            )

            self.tag_lower("shape")

        def fit_to_content(self):
            """Forces the canvas to shrink to the height of its inner content."""
            self.update_idletasks()
            req_height = self.inner_frame.winfo_reqheight() + 2 * self.padding
            self.config(height=req_height)


else:  # pragma: no cover - exercised when tkinter is unavailable

    class RoundedFrame:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "Tkinter is not available in this environment. "
                "GUI components cannot be created."
            )

        def fit_to_content(self):
            return
