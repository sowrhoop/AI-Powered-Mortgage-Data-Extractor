import os
import sys
import keyboard
import tkinter as tk
from tkinter import ttk
import logging
import asyncio
import json 
from tkinter import messagebox
from typing import List, Optional, Any
from PIL import Image
from io import BytesIO
import base64

from utils.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

import config 

from services.capture_service import ScreenshotCapture
from services.ai_analysis_service import AIAnalysisService
from ui.results_window import ResultsWindow
from ui.settings_window import SettingsWindow # Import the new SettingsWindow
from utils.common_utils import get_dpi_scale_factor, is_admin, run_as_admin
from models.document_entities import AnalysisResult, MortgageDocumentEntities

try:
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
    logger.info("Application set to DPI aware.")
except AttributeError:
    logger.warning("Failed to set process DPI aware. Screen capture accuracy might be affected on high DPI displays.")

class MortgageDocumentAnalyzerApp:
    def __init__(self):
        logger.info("Initializing MortgageDocumentAnalyzerApp...")
        self.root = tk.Tk()
        self.root.withdraw() # Keep the main root window hidden

        self.all_analysis_results: List[AnalysisResult] = []
        self.screenshots_taken_count: int = 0
        self.screenshots_processed_count: int = 0
        self.active_hotkey_hooks: List[Any] = []
        self.is_shutting_down = False # Flag to indicate shutdown process

        # Load settings immediately
        self._load_settings()

        self.dpi_scale_factor = get_dpi_scale_factor()
        logger.info(f"Detected DPI Scale Factor: {self.dpi_scale_factor}")

        # Initialize ScreenshotCapture without image optimization parameters for now
        self.screenshot_capture = ScreenshotCapture(
            self.root, 
            self.dpi_scale_factor
        )
        self.ai_analysis_service: Optional[AIAnalysisService] = None
        self.results_window: Optional[ResultsWindow] = None

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        logger.info("Asyncio event loop initialized in the main thread.")

        self._integrate_asyncio_with_tkinter()
        self._setup_hotkeys() # Initial setup of hotkeys from loaded config
        logger.info(f"Application initialized. Listening for hotkeys: {', '.join(config.HOTKEYS)}")

        self.loop.create_task(self._init_async_services())
        self.root.after(100, self._check_api_configs) # Check configs after a short delay

        self._init_ui_windows()

        # Set up a protocol for the root window closing (though it's withdrawn)
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)


    def _load_settings(self):
        """Loads application settings from a JSON file, or uses defaults."""
        try:
            if os.path.exists(config.SETTINGS_FILE_PATH):
                with open(config.SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # Apply loaded settings to config module
                # Only load OpenAI API Key for now as requested
                config.OPENAI_API_KEY = settings.get('OPENAI_API_KEY', config.OPENAI_API_KEY)
                
                # Hotkeys need special handling as they are a list
                loaded_hotkeys = settings.get('HOTKEYS')
                if isinstance(loaded_hotkeys, list):
                    config.HOTKEYS = loaded_hotkeys
                else:
                    logger.warning("Hotkeys loaded from settings file were not a list. Using default.")
                    # Re-initialize with default if malformed
                    config.HOTKEYS = os.getenv("HOTKEYS", 'ctrl+alt+m,ctrl+alt+a').split(',')
                    config.HOTKEYS = [h.strip() for h in config.HOTKEYS if h.strip()]

                logger.info(f"Settings loaded from {config.SETTINGS_FILE_PATH}")
            else:
                logger.info("Settings file not found. Using default configurations.")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding settings JSON from {config.SETTINGS_FILE_PATH}: {e}. Using default configurations.", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading settings: {e}. Using default configurations.", exc_info=True)

    def _save_settings(self, settings_to_save: dict):
        """Saves application settings to a JSON file."""
        try:
            # Ensure the directory exists before saving
            os.makedirs(os.path.dirname(config.SETTINGS_FILE_PATH), exist_ok=True)
            with open(config.SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=4, ensure_ascii=False)
            logger.info(f"Settings saved to {config.SETTINGS_FILE_PATH}")
        except Exception as e:
            logger.error(f"Failed to save settings to {config.SETTINGS_FILE_PATH}: {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Failed to save settings:\n{e}")


    def _integrate_asyncio_with_tkinter(self):
        """Integrates the asyncio event loop with the Tkinter main loop."""
        def run_async_tasks():
            if not self.is_shutting_down: # Only run if not shutting down
                self.loop.call_soon(self.loop.stop)
                self.loop.run_forever()
                self.root.after(10, run_async_tasks)
        logger.info("Integrating asyncio event loop with Tkinter main loop.")
        self.root.after(10, run_async_tasks)

    async def _init_async_services(self):
        """Initializes asynchronous services like AIAnalysisService."""
        # AIAnalysisService needs the latest API key from config
        self.ai_analysis_service = AIAnalysisService(config.OPENAI_API_KEY)
        logger.info("AIAnalysisService initialized asynchronously.")

    def _check_api_configs(self):
        """Checks if critical API configurations are set and shows an error if not."""
        if self.ai_analysis_service is None:
            self.root.after(100, self._check_api_configs) # Re-check after a delay if service not yet initialized
            return
        if not self.ai_analysis_service.is_configured:
            response = messagebox.askyesno(
                "Configuration Error",
                "OpenAI API Key is missing. Do you want to open settings to configure it?"
            )
            if response:
                self._open_settings_window()
            else:
                logger.critical("Application cannot proceed due to missing API configurations.")
                self.root.destroy()

    def _setup_hotkeys(self):
        """Registers global hotkeys for triggering the analysis workflow."""
        for hook in self.active_hotkey_hooks:
            try:
                keyboard.unhook(hook)
                logger.debug(f"Unhooked old hotkey: {hook}")
            except Exception as e:
                logger.warning(f"Failed to unhook hotkey {hook}: {e}")
        self.active_hotkey_hooks.clear()

        for hotkey in config.HOTKEYS:
            hook = keyboard.add_hotkey(hotkey, lambda: self.loop.create_task(self._run_analysis_workflow()))
            self.active_hotkey_hooks.append(hook)
            logger.debug(f"Registered hotkey: {hotkey}, Hook: {hook}")

    def _init_ui_windows(self):
        """Initializes and displays the ResultsWindow."""
        # Create a dummy result for initial display, or if no captures yet
        dummy_result = AnalysisResult(
            entities=MortgageDocumentEntities(),
            summary="",
            error=None,
            document_id="Document_0"
        )
        # Add a placeholder if the list is empty, otherwise use existing data
        if not self.all_analysis_results:
            self.all_analysis_results.append(dummy_result)
        
        logger.info(f"Initializing ResultsWindow with current data: {len(self.all_analysis_results)} results.")
        # Ensure ResultsWindow gets the close callback so main app can shut down
        self.results_window = ResultsWindow(
            self.root,
            self.all_analysis_results,
            on_new_input_callback=self._trigger_new_capture_for_current_session,
            on_close_callback=self._on_results_window_closed # Pass the new callback
        )
        self.results_window._position_window_on_right_half()
        self.results_window.add_settings_button(self._open_settings_window)
        self.results_window.set_capture_callbacks(
            on_new_capture_callback=self._trigger_new_capture_for_current_session,
            on_start_new_session_callback=self._start_new_session_callback
        )
        logger.info("ResultsWindow initialized and ready.")
        

    async def _run_analysis_workflow(self):
        """
        Main workflow for capturing a screenshot, analyzing it with AI,
        and updating the UI.
        """
        logger.info("Hotkey pressed. Initiating document capture workflow.")
        
        if self.is_shutting_down: # Prevent new workflows if shutting down
            logger.info("Application is shutting down, ignoring new capture request.")
            return

        # Ensure AIAnalysisService is configured before proceeding
        if not self.ai_analysis_service or not self.ai_analysis_service.is_configured:
            messagebox.showerror("Configuration Error", "AI analysis service is not configured. Please set your OpenAI API key in settings.")
            logger.error("AI analysis service not configured. Aborting workflow.")
            return

        try:
            logger.info("Waiting for user to select screen region...")
            coordinates = await self.loop.run_in_executor(None, self.screenshot_capture.select_region)
            selected_image = None
            if coordinates:
                selected_image = await self.loop.run_in_executor(None, self.screenshot_capture.crop_image, coordinates)
                self.screenshots_taken_count += 1

            if selected_image:
                logger.info("Screen region captured. Performing AI analysis...")
                image_bytes = self._convert_pil_to_bytes(selected_image)
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                # Add a placeholder result immediately for UI feedback
                placeholder_result = AnalysisResult(
                    entities=MortgageDocumentEntities(),
                    summary="Processing...",
                    error=None,
                    document_id=f"Document_{len(self.all_analysis_results) + 1}"
                )
                self.all_analysis_results.append(placeholder_result)
                self._update_ui_with_results(update_data=True)

                analysis_result = await self.ai_analysis_service.analyze_mortgage_document(
                    ocr_text="", # ocr_text is not used when base64_image is provided
                    base64_image=base64_image
                )
                # logger.info(f"AI analysis completed. Result: {analysis_result}")
                
                # Update the last added placeholder result with the actual data
                self.all_analysis_results[-1] = analysis_result
                if not analysis_result.document_id or analysis_result.document_id == "Unnamed Document":
                    analysis_result.document_id = f"Document_{len(self.all_analysis_results)}" # Re-assign based on final list size


                self.screenshots_processed_count += 1
                logger.info(f"Screenshot taken and processed. Total taken: {self.screenshots_taken_count}, Processed: {self.screenshots_processed_count}")
                logger.info("AI analysis completed. Displaying results.")
                self._update_ui_with_results(update_data=True, error_message=analysis_result.error)

            else:
                logger.info("Screen capture cancelled or failed.")
                # If capture was cancelled and no other results exist, clear the placeholder
                if len(self.all_analysis_results) == 1 and self.all_analysis_results[0].document_id == "Document_0":
                    self.all_analysis_results.clear() # Clear dummy if nothing happened
                self._update_ui_with_results(update_data=True) # Update to show empty state or previous results

        except Exception as e:
            logger.critical(f"An unhandled error occurred in analysis workflow: {e}", exc_info=True)
            error_msg = f"An unexpected error occurred: {e}"
            # Ensure an error result is shown if the workflow fails
            if not self.all_analysis_results or self.all_analysis_results[-1].summary == "Processing...":
                # If the last result was a placeholder or none exist, add/update with error
                error_result = AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=error_msg, document_id=f"Document_{len(self.all_analysis_results) + 1}_Error")
                if self.all_analysis_results and self.all_analysis_results[-1].summary == "Processing...":
                    self.all_analysis_results[-1] = error_result
                else:
                    self.all_analysis_results.append(error_result)
            else: # Add a new error result if there are existing valid results
                self.all_analysis_results.append(AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=error_msg, document_id=f"Document_{len(self.all_analysis_results) + 1}_Error"))
            
            self._update_ui_with_results(update_data=True, error_message=error_msg)
        finally:
            pass


    def _convert_pil_to_bytes(self, pil_image: Image.Image, dpi : int = 300) -> bytes:
        """Converts a PIL Image object to bytes in PNG format."""
        byte_arr = BytesIO()
        pil_image.save(byte_arr, format='PNG', dpi=(dpi, dpi))
        return byte_arr.getvalue()

    def _update_ui_with_results(self, update_data: bool, error_message: str = None):
        """Schedules UI update for ResultsWindow on the main Tkinter thread."""
        self.root.after(0, self._manage_results_window_visibility, True, update_data, error_message)

    def _manage_results_window_visibility(self, show: bool, update_data: bool = False, error_message: str = None):
        """Manages the visibility and data update of the ResultsWindow."""
        # Ensure current_results is always a list for update_data
        current_results = self.all_analysis_results

        # If an error occurred and no valid results are present, create a temporary result to display the error
        if error_message and not current_results:
            current_results = [AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=error_message, document_id="Error_Doc")]
            logger.warning(f"Displaying results with error: {error_message}")
        
        # If the results window hasn't been created yet or was destroyed
        if not self.results_window or not self.results_window.winfo_exists():
            if show:
                logger.info("Creating new ResultsWindow.")
                self.results_window = ResultsWindow(
                    self.root,
                    current_results,
                    on_new_input_callback=self._trigger_new_capture_for_current_session,
                    on_close_callback=self._on_results_window_closed
                )
                self.results_window._position_window_on_right_half()
                self.results_window.add_settings_button(self._open_settings_window)
                self.results_window.set_capture_callbacks(
                    on_new_capture_callback=self._trigger_new_capture_for_current_session,
                    on_start_new_session_callback=self._start_new_session_callback
                )
                # Ensure it's lifted and focused after creation
                self.results_window.lift()
                self.results_window.focus_force()
            else:
                # If told to hide but window doesn't exist, do nothing
                pass
        else: # If the results window already exists
            if show:
                logger.info("Updating existing ResultsWindow.")
                if update_data:
                    self.results_window.update_data(current_results)
                self.results_window.deiconify() # Restore if minimized/withdrawn
                self.results_window.lift()     # Bring to front
                self.results_window.focus_force() # Give focus
            else:
                self.results_window.withdraw() # Hide the window

    def _trigger_new_capture_for_current_session(self):
        """
        Triggers a new document capture and analysis, adding results to the current session.
        This is called by the "Capture New Document" button in ResultsWindow.
        """
        logger.info("User requested new document capture for current session.")
        # Ensure results window is visible and focused before capture starts
        if self.results_window:
            self.results_window.deiconify()
            self.results_window.lift()
            self.results_window.focus_force()
        
        # Start the async workflow task
        self.loop.create_task(self._run_analysis_workflow())


    def _start_new_session_callback(self):
        """
        Clears all stored analysis results and resets the session.
        This is called by the "Start New Session" button in ResultsWindow.
        """
        logger.info("User requested to start a new session. Clearing all stored results.")
        self.all_analysis_results.clear()
        self.screenshots_taken_count = 0
        self.screenshots_processed_count = 0
        # Re-add the dummy result for initial state after clearing
        self.all_analysis_results.append(AnalysisResult(
            entities=MortgageDocumentEntities(),
            summary="",
            error=None,
            document_id="Document_0"
        ))
        self._manage_results_window_visibility(show=True, update_data=True)
        logger.info("UI refreshed and ready for new input.")

    def _open_settings_window(self):
        """Opens the settings configuration window."""
        logger.info("Opening settings window.")
        current_settings = {
            'OPENAI_API_KEY': config.OPENAI_API_KEY,
            # MAX_IMAGE_DIMENSION and JPEG_QUALITY are not exposed in settings_window for now
            'HOTKEYS': config.HOTKEYS # Hotkeys are displayed but not edited via settings window directly
        }
        settings_dialog = SettingsWindow(self.root, current_settings, self._apply_settings)
        settings_dialog.focus_set()
        settings_dialog.grab_set() # Make it modal

    def _apply_settings(self, new_settings: dict):
        """Applies the new settings received from the settings window and saves them."""
        logger.info(f"Applying new settings: {new_settings}")
        
        # Update config module variables directly for API Key only as requested
        # Check if API key actually changed before re-initializing service
        if config.OPENAI_API_KEY != new_settings['OPENAI_API_KEY']:
            config.OPENAI_API_KEY = new_settings['OPENAI_API_KEY']
            logger.info("OpenAI API key changed. Re-initializing AIAnalysisService.")
            self.loop.create_task(self._init_async_services())
        else:
            logger.info("OpenAI API key did not change.")

        # Save the new settings to file after applying them
        self._save_settings(new_settings)

    def _on_results_window_closed(self):
        """Callback from ResultsWindow when it's closed, triggering app shutdown."""
        logger.info("Results window closed. Initiating application shutdown.")
        self.is_shutting_down = True
        self.root.quit() # This will stop the Tkinter mainloop

    def on_app_close(self):
        """Handles the main application root window closing."""
        logger.info("Main application root window closing (via root window close protocol).")
        self.is_shutting_down = True
        self.root.quit()

    def run(self):
        """Starts the Tkinter main loop."""
        self.root.mainloop()
        # After mainloop exits, ensure asyncio loop is also closed
        logger.info("Tkinter main loop exited. Closing asyncio loop.")
        if not self.loop.is_closed():
            self.loop.close()
        logger.info("Application shut down.")


if __name__ == "__main__":
    app = MortgageDocumentAnalyzerApp()
    app.run()