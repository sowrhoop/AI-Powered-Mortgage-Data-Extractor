import tkinter as tk
from PIL import Image, ImageGrab
import time
import logging

logger = logging.getLogger(__name__)

class ScreenshotCapture:
    def __init__(self, parent_tk_root: tk.Tk, dpi_scale=1.0):
        self.parent_tk_root = parent_tk_root
        self.selection_window = None
        self.canvas = None
        self.rect_id = None
        self.start_x, self.start_y, self.end_x, self.end_y = 0, 0, 0, 0
        self.selection_made = False

    def select_region(self):
        self.selection_window = tk.Toplevel(self.parent_tk_root)
        self.selection_window.attributes("-fullscreen", True)
        self.selection_window.attributes("-alpha", 0.3)
        self.selection_window.attributes("-topmost", True)
        self.selection_window.configure(background='grey')
        self.selection_window.overrideredirect(True)

        self.canvas = tk.Canvas(self.selection_window, cursor="cross", bg="grey", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)

        self.selection_window.bind("<Escape>", self._on_escape_key)

        self.rect_id = self.canvas.create_rectangle(0, 0, 0, 0, outline="red", width=2)

        logger.info("Select the area to capture using your mouse (drag and release). Press ESC to cancel...")

        self.parent_tk_root.wait_window(self.selection_window)

        if self.selection_made:
            x1, x2 = sorted([self.start_x, self.end_x])
            y1, y2 = sorted([self.start_y, self.end_y])

            logger.info(f"Selected screen region (physical pixels): ({x1}, {y1}) to ({x2}, {y2})")
            return (x1, y1, x2, y2)
        else:
            logger.info("Screen region selection cancelled.")
            return None

    def _on_mouse_press(self, event):
        self.start_x = self.selection_window.winfo_pointerx()
        self.start_y = self.selection_window.winfo_pointery()
        self.selection_made = False

    def _on_mouse_drag(self, event):
        self.end_x = self.selection_window.winfo_pointerx()
        self.end_y = self.selection_window.winfo_pointery()
        if self.start_x is not None and self.start_y is not None:
            self.canvas.coords(
                self.rect_id,
                self.start_x - self.selection_window.winfo_rootx(),
                self.start_y - self.selection_window.winfo_rooty(),
                self.end_x - self.selection_window.winfo_rootx(),
                self.end_y - self.selection_window.winfo_rooty()
            )

    def _on_mouse_release(self, event):
        self.end_x = self.selection_window.winfo_pointerx()
        self.end_y = self.selection_window.winfo_pointery()
        if abs(self.end_x - self.start_x) > 5 and abs(self.end_y - self.start_y) > 5:
            self.selection_made = True
        self.selection_window.destroy()

    def _on_escape_key(self, event):
        self.selection_made = False
        self.selection_window.destroy()

    def crop_image(self, coordinates):
        if not coordinates or len(coordinates) != 4:
            logger.error("Invalid coordinates provided for cropping.")
            return None

        x1, y1, x2, y2 = coordinates
        if x1 == x2 or y1 == y2:
            logger.warning("Selected region is too small or invalid for cropping.")
            return None

        img_full = None
        img_cropped = None
        returned_image = None
        try:
            img_full = ImageGrab.grab()
            logger.info(f"Full screen captured. Image dimensions: {img_full.size}")

            img_cropped = img_full.crop((x1, y1, x2, y2))
            logger.info(f"Image cropped to region: ({x1}, {y1}, {x2}, {y2}). Cropped dimensions: {img_cropped.size}")
            returned_image = img_cropped
            return img_cropped
        except Exception as e:
            logger.error(f"Error during screen capture or cropping: {e}", exc_info=True)
            return None
        finally:
            if img_full:
                img_full.close()
            if img_cropped and img_cropped is not returned_image:
                img_cropped.close()