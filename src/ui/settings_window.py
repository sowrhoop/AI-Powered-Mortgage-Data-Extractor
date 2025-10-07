import tkinter as tk
from tkinter import ttk, messagebox
import logging
import config
from utils.common_utils import get_work_area

logger = logging.getLogger(__name__)

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, current_settings: dict, on_save_callback: callable):
        super().__init__(parent)
        logger.info("SettingsWindow: Initializing...")
        self.title("Application Settings")
        self.geometry("450x360")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.current_settings = current_settings
        self.on_save_callback = on_save_callback
        self.settings_vars = {}

        self._create_widgets()
        self._load_current_settings()
        self._center_window()

        logger.info("SettingsWindow: Initialized and displayed.")

    def _center_window(self):
        self.update_idletasks()
        # Ensure the window is large enough to show all content/buttons
        try:
            req_w = max(self.winfo_width(), self.winfo_reqwidth(), 450)
            req_h = max(self.winfo_height(), self.winfo_reqheight(), 360)
        except Exception:
            req_w, req_h = 450, 360

        left, top, right, bottom = get_work_area()
        work_w = max(0, right - left)
        work_h = max(0, bottom - top)

        width = min(req_w, max(320, work_w - 20))
        height = min(req_h, max(240, work_h - 20))

        x = left + (work_w - width) // 2
        y = top + (work_h - height) // 2
        self.geometry(f"{int(width)}x{int(height)}+{int(x)}+{int(y)}")
        logger.debug(f"SettingsWindow: Centered within work area at ({x},{y}), size {width}x{height}")

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(expand=True, fill=tk.BOTH)

        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=0)

        row = 0

        ttk.Label(main_frame, text="OpenAI API Key:").grid(row=row, column=0, sticky="w", pady=5, padx=5)
        api_key_var = tk.StringVar(self)
        api_key_entry = ttk.Entry(main_frame, textvariable=api_key_var, width=40, show='*')
        api_key_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        show_api_var = tk.BooleanVar(self, value=False)
        def _toggle_show_api():
            api_key_entry.config(show='' if show_api_var.get() else '*')
        show_chk = ttk.Checkbutton(main_frame, text="Show", variable=show_api_var, command=_toggle_show_api)
        show_chk.grid(row=row, column=2, sticky="w", padx=2)
        self.settings_vars['OPENAI_API_KEY'] = api_key_var
        row += 1
        ttk.Label(main_frame, text="Saved to settings.json", font=("Arial", 8, "italic")).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # OpenAI Model
        ttk.Label(main_frame, text="OpenAI Model:").grid(row=row, column=0, sticky="w", pady=5, padx=5)
        model_var = tk.StringVar(self)
        model_entry = ttk.Entry(main_frame, textvariable=model_var, width=40)
        model_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        self.settings_vars['OPENAI_MODEL'] = model_var
        row += 1
        ttk.Label(main_frame, text=f"Default: {getattr(config, 'OPENAI_MODEL', '')}", font=("Arial", 8, "italic")).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # OpenAI Timeout (seconds)
        ttk.Label(main_frame, text="OpenAI Timeout (sec):").grid(row=row, column=0, sticky="w", pady=5, padx=5)
        timeout_var = tk.StringVar(self)
        timeout_entry = ttk.Entry(main_frame, textvariable=timeout_var, width=40)
        timeout_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        self.settings_vars['OPENAI_TIMEOUT'] = timeout_var
        row += 1
        ttk.Label(main_frame, text=f"Default: {getattr(config, 'OPENAI_TIMEOUT', '')}", font=("Arial", 8, "italic")).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # UI Confidence Threshold
        ttk.Label(main_frame, text="UI Min Confidence (0-1):").grid(row=row, column=0, sticky="w", pady=5, padx=5)
        ui_conf_var = tk.StringVar(self)
        ui_conf_entry = ttk.Entry(main_frame, textvariable=ui_conf_var, width=40)
        ui_conf_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        self.settings_vars['UI_CONFIDENCE_MIN'] = ui_conf_var
        row += 1
        ttk.Label(main_frame, text=f"Default: {getattr(config, 'UI_CONFIDENCE_MIN', '')}", font=("Arial", 8, "italic")).grid(row=row, column=1, sticky="w", padx=5)
        row += 1
        
        ttk.Label(main_frame, text="Current Hotkeys:").grid(row=row, column=0, sticky="nw", pady=5, padx=5)
        hotkeys_text = tk.Text(main_frame, height=1, width=40, wrap=tk.WORD, state=tk.DISABLED)
        hotkeys_text.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        self.settings_vars['HOTKEYS_DISPLAY'] = hotkeys_text
        ttk.Label(main_frame, text="Configured in settings.json (not editable here)", font=("Arial", 8, "italic")).grid(row=row+1, column=1, sticky="w", padx=5)
        row += 2

        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)
        button_frame.columnconfigure(2, weight=0)

        self.save_button = ttk.Button(button_frame, text="Save", command=self._on_save)
        self.save_button.grid(row=0, column=1, padx=5)

        cancel_button = ttk.Button(button_frame, text="Close", command=self.destroy)
        cancel_button.grid(row=0, column=2, padx=5)

    def _load_current_settings(self):
        self.settings_vars['OPENAI_API_KEY'].set(self.current_settings.get('OPENAI_API_KEY', ''))
        self.settings_vars['OPENAI_MODEL'].set(self.current_settings.get('OPENAI_MODEL', ''))
        # Display numeric values as strings
        self.settings_vars['OPENAI_TIMEOUT'].set(str(self.current_settings.get('OPENAI_TIMEOUT', '')))
        self.settings_vars['UI_CONFIDENCE_MIN'].set(str(self.current_settings.get('UI_CONFIDENCE_MIN', '')))
        
        hotkeys_display_widget = self.settings_vars['HOTKEYS_DISPLAY']
        hotkeys_display_widget.config(state=tk.NORMAL)
        hotkeys_display_widget.delete(1.0, tk.END)
        hotkeys_display_widget.insert(tk.END, ", ".join(self.current_settings.get('HOTKEYS', [])))
        hotkeys_display_widget.config(state=tk.DISABLED)

    def _on_save(self):
        new_settings = {}
        errors = []

        api_key = self.settings_vars['OPENAI_API_KEY'].get().strip()
        if not api_key:
            errors.append("OpenAI API Key cannot be empty.")
        new_settings['OPENAI_API_KEY'] = api_key;

        # Model validation
        model = self.settings_vars['OPENAI_MODEL'].get().strip()
        if not model:
            errors.append("OpenAI Model cannot be empty.")
        new_settings['OPENAI_MODEL'] = model

        # Timeout validation
        timeout_raw = self.settings_vars['OPENAI_TIMEOUT'].get().strip()
        try:
            timeout_val = float(timeout_raw)
            if timeout_val <= 0:
                raise ValueError
            new_settings['OPENAI_TIMEOUT'] = timeout_val
        except Exception:
            errors.append("OpenAI Timeout must be a positive number.")

        # UI confidence validation
        ui_conf_raw = self.settings_vars['UI_CONFIDENCE_MIN'].get().strip()
        try:
            ui_conf_val = float(ui_conf_raw)
            if ui_conf_val < 0.0 or ui_conf_val > 1.0:
                raise ValueError
            new_settings['UI_CONFIDENCE_MIN'] = ui_conf_val
        except Exception:
            errors.append("UI Min Confidence must be a number between 0 and 1.")

        new_settings['HOTKEYS'] = self.current_settings.get('HOTKEYS', [])

        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            logger.warning(f"Settings validation failed: {errors}")
            return

        try:
            self.on_save_callback(new_settings)
            logger.info("Settings callback called with new settings.")
            # Subtle inline confirmation instead of a popup
            try:
                self._flash_button(self.save_button, "Saved ✓")
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred while saving settings: {e}")
            logger.error(f"Error during settings save callback: {e}", exc_info=True)

    def _flash_button(self, btn: ttk.Button, flash_text: str = "Done ✓", duration_ms: int = 1200):
        try:
            if not btn or not btn.winfo_exists():
                return
            original = btn["text"]
            btn.config(text=flash_text)
            btn.state(["disabled"])  # avoid double clicks
            def _restore():
                if btn and btn.winfo_exists():
                    btn.config(text=original)
                    try:
                        btn.state(["!disabled"])  # re-enable
                    except Exception:
                        pass
            self.after(duration_ms, _restore)
        except Exception:
            pass