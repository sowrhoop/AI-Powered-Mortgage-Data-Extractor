import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)

class SettingsWindow(tk.Toplevel):
    """
    A window for configuring application settings such as API keys.
    """
    def __init__(self, parent: tk.Tk, current_settings: dict, on_save_callback: callable):
        """
        Initializes the SettingsWindow.

        :param parent: The parent Tkinter window.
        :param current_settings: A dictionary containing the current application settings.
                                 Expected keys: 'OPENAI_API_KEY'.
        :param on_save_callback: A callback function to be called with updated settings
                                 when the user clicks 'Save'.
        """
        super().__init__(parent)
        logger.info("SettingsWindow: Initializing...")
        self.title("Application Settings")
        self.geometry("450x180") # Adjusted size for fewer settings
        self.resizable(False, False)
        self.attributes("-topmost", True) # Keep settings window on top

        self.current_settings = current_settings
        self.on_save_callback = on_save_callback
        self.settings_vars = {} # To hold Tkinter StringVars for settings

        self._create_widgets()
        self._load_current_settings()
        self._center_window() # Center the settings window

        logger.info("SettingsWindow: Initialized and displayed.")

    def _center_window(self):
        """Centers the settings window on the screen."""
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = self.winfo_width()
        window_height = self.winfo_height()

        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"+{x}+{y}")
        logger.debug(f"SettingsWindow: Centered at ({x},{y})")

    def _create_widgets(self):
        """Creates the input widgets for various settings."""
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Configure grid columns for labels and entries
        main_frame.columnconfigure(0, weight=0) # Labels
        main_frame.columnconfigure(1, weight=1) # Entries

        row = 0

        # OpenAI API Key
        ttk.Label(main_frame, text="OpenAI API Key:").grid(row=row, column=0, sticky="w", pady=5, padx=5)
        api_key_var = tk.StringVar(self)
        api_key_entry = ttk.Entry(main_frame, textvariable=api_key_var, width=40, show='*') # Show * for security
        api_key_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        self.settings_vars['OPENAI_API_KEY'] = api_key_var
        row += 1
        
        # Display Hotkeys (non-editable for now as per request)
        ttk.Label(main_frame, text="Current Hotkeys:").grid(row=row, column=0, sticky="nw", pady=5, padx=5)
        hotkeys_text = tk.Text(main_frame, height=1, width=40, wrap=tk.WORD, state=tk.DISABLED)
        hotkeys_text.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        self.settings_vars['HOTKEYS_DISPLAY'] = hotkeys_text # Store reference to text widget
        ttk.Label(main_frame, text="(Edit via environment variable HOTKEYS)", font=("Arial", 8, "italic")).grid(row=row+1, column=1, sticky="w", padx=5)
        row += 2 # Increment row by 2 for the hotkeys and info label


        # Buttons
        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        button_frame.columnconfigure(0, weight=1) # Spacer
        button_frame.columnconfigure(1, weight=0) # Save button
        button_frame.columnconfigure(2, weight=0) # Cancel button

        save_button = ttk.Button(button_frame, text="Save", command=self._on_save)
        save_button.grid(row=0, column=1, padx=5)

        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.destroy)
        cancel_button.grid(row=0, column=2, padx=5)

    def _load_current_settings(self):
        """Loads current settings into the Tkinter variables."""
        self.settings_vars['OPENAI_API_KEY'].set(self.current_settings.get('OPENAI_API_KEY', ''))
        
        # For hotkeys, display them in the Text widget
        hotkeys_display_widget = self.settings_vars['HOTKEYS_DISPLAY']
        hotkeys_display_widget.config(state=tk.NORMAL)
        hotkeys_display_widget.delete(1.0, tk.END)
        hotkeys_display_widget.insert(tk.END, ", ".join(self.current_settings.get('HOTKEYS', [])))
        hotkeys_display_widget.config(state=tk.DISABLED)


    def _on_save(self):
        """Handles the Save button click, validates input, and calls the callback."""
        new_settings = {}
        errors = []

        # Validate OpenAI API Key
        api_key = self.settings_vars['OPENAI_API_KEY'].get().strip()
        if not api_key:
            errors.append("OpenAI API Key cannot be empty.")
        new_settings['OPENAI_API_KEY'] = api_key

        # Hotkeys are display-only in this window, so we just pass the existing ones
        new_settings['HOTKEYS'] = self.current_settings.get('HOTKEYS', [])


        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            logger.warning(f"Settings validation failed: {errors}")
            return

        try:
            self.on_save_callback(new_settings)
            self.destroy() # Close the settings window immediately
            messagebox.showinfo("Settings Saved", "Application settings updated successfully.")
            logger.info("Settings saved successfully and window closed.")
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred while saving settings: {e}")
            logger.error(f"Error during settings save callback: {e}", exc_info=True)