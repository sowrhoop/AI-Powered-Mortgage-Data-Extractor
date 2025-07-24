import os
import sys
import time
import keyboard
import tkinter as tk
from tkinter import ttk # Import ttk for themed widgets
import logging
import subprocess
import threading # Import threading module
from tkinter import messagebox # Import messagebox for user-friendly error pop-ups
from typing import List # Import List for type hinting

# Configure logging for the application
from utils.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# Import configuration and services
from config import AZURE_VISION_KEY, AZURE_VISION_ENDPOINT, OPENAI_API_KEY, HOTKEYS, OUTPUT_FILE_NAME
from services.capture_service import ScreenshotCapture
from services.ocr_service import OCRService
from services.ai_analysis_service import AIAnalysisService
from ui.results_window import ResultsWindow
# Removed: from ui.processing_window import ProcessingWindow # No longer needed
from utils.common_utils import get_base_path, get_dpi_scale_factor, is_admin, run_as_admin
from models.document_entities import AnalysisResult, MortgageDocumentEntities # Import for default error result

# Make the application DPI-aware for accurate screen capture on high DPI displays
# This helps ensure that the captured region matches the visual selection
try:
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
    logger.info("Application set to DPI aware.")
except AttributeError:
    logger.warning("Failed to set process DPI aware. Screen capture accuracy might be affected on high DPI displays.")


class MortgageDocumentAnalyzerApp:
    """
    Main application class for the Mortgage Document Analyzer.
    Manages the UI, hotkey listeners, and orchestrates the document analysis workflow.
    """
    def __init__(self):
        logger.info("Initializing MortgageDocumentAnalyzerApp...")
        self.root = tk.Tk()
        self.root.withdraw() # Hide the main Tkinter window

        self.all_analysis_results: List[AnalysisResult] = [] # Stores results of all analyses

        self.dpi_scale_factor = get_dpi_scale_factor()
        logger.info(f"Detected DPI Scale Factor: {self.dpi_scale_factor}")

        # Initialize services
        self.screenshot_capture = ScreenshotCapture(self.root, self.dpi_scale_factor)
        self.ocr_service = OCRService(AZURE_VISION_ENDPOINT, AZURE_VISION_KEY)
        self.ai_analysis_service = AIAnalysisService(OPENAI_API_KEY)

        self.results_window: ResultsWindow = None # Will be initialized when results are ready
        # Removed: self.processing_window: ProcessingWindow = ProcessingWindow(self.root) # No longer needed

        self._setup_hotkeys()
        logger.info(f"Application initialized. Listening for hotkeys: {', '.join(HOTKEYS)}")

        # Check if API keys are configured
        if not self.ocr_service.is_configured or not self.ai_analysis_service.is_configured:
            messagebox.showerror(
                "Configuration Error",
                "Azure Vision API Key or Endpoint, or OpenAI API Key is missing. "
                "Please set the environment variables AZURE_VISION_KEY, AZURE_VISION_ENDPOINT, and OPENAI_API_KEY."
            )
            logger.critical("Application cannot proceed due to missing API configurations.")
            self.root.destroy() # Close the hidden root window and exit

    def _setup_hotkeys(self):
        """
        Sets up global hotkeys to trigger the screen capture process.
        """
        for hotkey in HOTKEYS:
            keyboard.add_hotkey(hotkey, self._on_hotkey_pressed)
            logger.debug(f"Registered hotkey: {hotkey}")

    def _on_hotkey_pressed(self):
        """
        Callback function executed when a registered hotkey is pressed.
        Initiates the screen capture and analysis workflow.
        """
        logger.info("Hotkey pressed. Initiating document capture workflow.")
        # Ensure the results window is hidden before starting new capture
        if self.results_window and self.results_window.winfo_exists():
            self.results_window.withdraw()

        # Run the capture and analysis in a separate thread to keep UI responsive
        threading.Thread(target=self._run_analysis_workflow).start()

    def _run_analysis_workflow(self):
        """
        Executes the full document analysis workflow: capture, OCR, AI analysis, and display.
        This runs in a separate thread.
        """
        try:
            # Step 1: Capture screen region
            logger.info("Waiting for user to select screen region...")
            coordinates = self.screenshot_capture.select_region()
            selected_image = None
            if coordinates:
                selected_image = self.screenshot_capture.crop_image(coordinates)

            if selected_image:
                logger.info("Screen region captured. Performing OCR and AI analysis...")
                
                # Ensure results window exists and is visible before showing processing message
                if not self.results_window or not self.results_window.winfo_exists():
                    # Create it with an empty list to show "Ready for new document" initially
                    self.results_window = ResultsWindow(
                        self.root,
                        [], # Pass an empty list
                        self._on_new_input_callback_from_results_ui
                    )
                else:
                    self.results_window.deiconify() # Ensure it's not minimized
                    self.results_window.lift() # Bring to front
                    self.results_window.focus_force() # Give focus

                self.results_window.show_processing_message() # NEW: Show processing message in ResultsWindow
                
                # Step 2: Perform OCR
                image_bytes = self._convert_pil_to_bytes(selected_image)
                ocr_text = self.ocr_service.perform_ocr(image_bytes)

                if ocr_text:
                    # Step 3: Perform AI Analysis
                    analysis_result = self.ai_analysis_service.analyze_mortgage_document(ocr_text)
                    self.all_analysis_results.append(analysis_result) # Add new result to the list

                    logger.info("AI analysis completed. Displaying results.")
                    self.results_window.hide_processing_message() # NEW: Hide processing message
                    # Step 4: Display results in UI
                    self._display_results()
                else:
                    self.results_window.hide_processing_message() # NEW: Hide processing message on OCR error
                    messagebox.showerror("OCR Error", "Failed to extract text from the captured image.")
                    logger.error("OCR failed, no text extracted.")
                    self._display_results(error_message="OCR failed to extract text.")
            else:
                logger.info("Screen capture cancelled or failed.")
                # If capture is cancelled, ensure results window is brought back if it was previously open
                if self.results_window and not self.results_window.winfo_exists():
                    # If window was destroyed (e.g., by user closing it), re-create it with existing data
                    self._display_results()
                elif self.results_window:
                    # If it was just withdrawn, bring it back
                    self.results_window.deiconify() # Or .lift() and .focus_force()
                    self.results_window.lift()
                    self.results_window.focus_force()

        except Exception as e:
            logger.critical(f"An unhandled error occurred in analysis workflow: {e}", exc_info=True)
            if self.results_window and self.results_window.winfo_exists():
                self.results_window.hide_processing_message() # NEW: Hide processing message on unexpected error
            messagebox.showerror("Application Error", f"An unexpected error occurred: {e}")
            self._display_results(error_message=f"An unexpected error occurred: {e}")


    def _convert_pil_to_bytes(self, pil_image):
        """Converts a PIL Image object to bytes (PNG format)."""
        from io import BytesIO
        byte_arr = BytesIO()
        pil_image.save(byte_arr, format='PNG')
        return byte_arr.getvalue()

    def _display_results(self, error_message: str = None):
        """
        Displays the analysis results in a dedicated Tkinter window.
        Creates the window if it doesn't exist, or updates its content if it does.
        """
        # If there's an error message and no previous results, create a dummy result for display
        if error_message and not self.all_analysis_results:
            dummy_result = AnalysisResult(
                entities=MortgageDocumentEntities(),
                summary="",
                error=error_message
            )
            # Temporarily add to a list to pass to ResultsWindow, but don't store permanently
            temp_results = [dummy_result]
            logger.warning(f"Displaying results with error: {error_message}")
        else:
            temp_results = self.all_analysis_results # Use the actual stored results

        if not self.results_window or not self.results_window.winfo_exists():
            logger.info("Creating new ResultsWindow.")
            self.results_window = ResultsWindow(
                self.root,
                temp_results, # Pass the (potentially empty or error-containing) list
                self._on_new_input_callback_from_results_ui # Pass the callback for the button
            )
        else:
            logger.info("Updating existing ResultsWindow.")
            self.results_window.update_data(temp_results) # Update with the latest data
            self.results_window.deiconify() # Ensure it's not minimized
            self.results_window.lift() # Bring to front
            self.results_window.focus_force() # Give focus

    def _on_new_input_callback_from_results_ui(self):
        """
        Callback for 'Capture New Document' button in the results UI.
        Clears the stored results and prepares for a new capture, but does NOT
        immediately launch the screenshot.
        """
        logger.info("User requested new document capture. Clearing stored results.")
        self.all_analysis_results.clear() # Clear the main list of results

        # Update the results window to reflect the cleared state
        if self.results_window and self.results_window.winfo_exists():
            self.results_window.update_data(self.all_analysis_results) # Pass the now empty list
            self.results_window.deiconify() # Ensure it's visible
            self.results_window.lift() # Bring to front
            self.results_window.focus_force() # Give focus
            self.results_window.withdraw() # Hide it again to allow new capture

        logger.info("UI cleared. Waiting for hotkey to initiate new screenshot capture.")
        # No call to self._on_hotkey_pressed() here. The app will now wait for a hotkey.

    def run(self):
        """
        Starts the main application loop. This keeps the script alive
        to listen for hotkey presses and manage UI events.
        """
        # This loop is necessary to keep the Tkinter event listener alive
        # for hotkey detection and UI interactions.
        self.root.mainloop()

if __name__ == "__main__":
    app = MortgageDocumentAnalyzerApp()
    app.run()
