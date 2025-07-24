import tkinter as tk
from PIL import Image, ImageGrab
import time
import logging

logger = logging.getLogger(__name__)

class ScreenshotCapture:
    """
    Manages screen region selection and image capture.
    Provides a transparent overlay for users to select an area.
    """
    def __init__(self, parent_tk_root: tk.Tk, dpi_scale=1.0):
        """
        Initializes the screenshot capture service.
        :param parent_tk_root: The main Tkinter root window. All Toplevels will be parented to this.
        :param dpi_scale: The DPI scaling factor of the display.
                          Important for accurate coordinate mapping on high-DPI screens.
        """
        self.parent_tk_root = parent_tk_root # Store the main Tkinter root
        self.selection_window = None # This will be the Toplevel window for selection
        self.canvas = None
        self.rect_id = None
        self.start_x, self.start_y, self.end_x, self.end_y = 0, 0, 0, 0
        self.selection_made = False # Flag to indicate if a valid selection was made

    def select_region(self):
        """
        Opens a fullscreen, transparent Toplevel window to allow the user to select a screen region.
        Returns the selected coordinates (x1, y1, x2, y2) or None if cancelled.
        """
        # Create a Toplevel window parented to the main hidden root
        self.selection_window = tk.Toplevel(self.parent_tk_root)
        # Set window attributes for fullscreen, transparency, and always on top
        self.selection_window.attributes("-fullscreen", True)
        self.selection_window.attributes("-alpha", 0.3) # Make it semi-transparent
        self.selection_window.attributes("-topmost", True) # Keep it on top of other windows
        self.selection_window.configure(background='grey') # Background color for the overlay
        self.selection_window.overrideredirect(True) # Remove window decorations (title bar, borders)

        self.canvas = tk.Canvas(self.selection_window, cursor="cross", bg="grey", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bind mouse events for drawing the selection rectangle
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)

        # Bind Escape key to cancel the selection
        self.selection_window.bind("<Escape>", self._on_escape_key)

        # Initialize the selection rectangle (initially invisible)
        self.rect_id = self.canvas.create_rectangle(0, 0, 0, 0, outline="red", width=2)

        logger.info("Select the area to capture using your mouse (drag and release). Press ESC to cancel...")

        # Use wait_window to pause the main Tkinter thread until this Toplevel is destroyed
        # This is the correct way to make the main thread wait for a Toplevel
        self.parent_tk_root.wait_window(self.selection_window)

        # After wait_window returns (meaning self.selection_window has been destroyed)
        if self.selection_made:
            # Ensure coordinates are sorted (x1, y1, x2, y2) where x1<x2, y1<y2
            x1, x2 = sorted([self.start_x, self.end_x])
            y1, y2 = sorted([self.start_y, self.end_y])

            # Tkinter's winfo_pointerx/y give physical screen coordinates.
            # ImageGrab.grab() also operates on physical screen coordinates.
            # So, explicit DPI scaling on these coordinates is generally not needed here
            # unless there's a specific configuration where Tkinter reports virtual pixels.
            logger.info(f"Selected screen region (physical pixels): ({x1}, {y1}) to ({x2}, {y2})")
            return (x1, y1, x2, y2)
        else:
            logger.info("Screen region selection cancelled.")
            return None

    def _on_mouse_press(self, event):
        """Event handler for mouse button press (start of selection)."""
        # Get global screen X/Y coordinates from the event
        self.start_x = self.selection_window.winfo_pointerx()
        self.start_y = self.selection_window.winfo_pointery()
        self.selection_made = False # Reset flag

    def _on_mouse_drag(self, event):
        """Event handler for mouse dragging (drawing the rectangle)."""
        self.end_x = self.selection_window.winfo_pointerx()
        self.end_y = self.selection_window.winfo_pointery()
        # Update rectangle coordinates relative to the canvas
        if self.start_x is not None and self.start_y is not None:
            self.canvas.coords(
                self.rect_id,
                self.start_x - self.selection_window.winfo_rootx(), # Adjust for window's own position
                self.start_y - self.selection_window.winfo_rooty(),
                self.end_x - self.selection_window.winfo_rootx(),
                self.end_y - self.selection_window.winfo_rooty()
            )

    def _on_mouse_release(self, event):
        """Trigger region capture on mouse release."""
        self.end_x = self.selection_window.winfo_pointerx()
        self.end_y = self.selection_window.winfo_pointery()
        # Check if a meaningful selection was made (not just a tiny click)
        if abs(self.end_x - self.start_x) > 5 and abs(self.end_y - self.start_y) > 5:
            self.selection_made = True
        self.selection_window.destroy() # Destroy the Toplevel window

    def _on_escape_key(self, event):
        """Event handler for Escape key press (cancel selection)."""
        self.selection_made = False
        self.selection_window.destroy() # Destroy the Toplevel window

    def crop_image(self, coordinates):
        """
        Captures the full screen and crops it to the specified coordinates.
        :param coordinates: A tuple (x1, y1, x2, y2) defining the crop region.
        :return: A PIL Image object of the cropped region, or None if an error occurs.
        """
        if not coordinates or len(coordinates) != 4:
            logger.error("Invalid coordinates provided for cropping.")
            return None

        x1, y1, x2, y2 = coordinates
        # Ensure coordinates define a valid, non-empty region
        if x1 == x2 or y1 == y2:
            logger.warning("Selected region is too small or invalid for cropping.")
            return None

        try:
            # Capture the full screen using ImageGrab
            # ImageGrab.grab() captures the entire virtual screen (all monitors)
            img_full = ImageGrab.grab()
            logger.info(f"Full screen captured. Image dimensions: {img_full.size}")

            # Crop the image to the selected region
            img_cropped = img_full.crop((x1, y1, x2, y2))
            logger.info(f"Image cropped to region: ({x1}, {y1}, {x2}, {y2}). Cropped dimensions: {img_cropped.size}")
            return img_cropped
        except Exception as e:
            logger.error(f"Error during screen capture or cropping: {e}", exc_info=True)
            return None

