import os
import sys
import time
import keyboard
import tkinter as tk
from tkinter import ttk
import logging
import subprocess
import asyncio
from tkinter import messagebox
from typing import List, Optional
from PIL import Image
from io import BytesIO
import base64

from utils.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from config import OPENAI_API_KEY, HOTKEYS, OUTPUT_FILE_NAME
from services.capture_service import ScreenshotCapture
from services.ai_analysis_service import AIAnalysisService
from ui.results_window import ResultsWindow
from utils.common_utils import get_base_path, get_dpi_scale_factor, is_admin, run_as_admin
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
        self.root.withdraw()

        self.all_analysis_results: List[AnalysisResult] = []

        self.dpi_scale_factor = get_dpi_scale_factor()
        logger.info(f"Detected DPI Scale Factor: {self.dpi_scale_factor}")

        self.screenshot_capture = ScreenshotCapture(self.root, self.dpi_scale_factor)
        self.ai_analysis_service: Optional[AIAnalysisService] = None
        self.results_window: Optional[ResultsWindow] = None

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        logger.info("Asyncio event loop initialized in the main thread.")

        self._integrate_asyncio_with_tkinter()
        self._setup_hotkeys()
        logger.info(f"Application initialized. Listening for hotkeys: {', '.join(HOTKEYS)}")

        self.loop.create_task(self._init_async_services())
        self.root.after(100, self._check_api_configs)

        # ✅ Show ResultsWindow UI immediately with a dummy result
        dummy_result = AnalysisResult(
            entities=MortgageDocumentEntities(),
            summary="",
            error=None,
            document_id="Document_0"
        )
        self.all_analysis_results.append(dummy_result)
        self._manage_results_window_visibility(show=True, update_data=True)

    def _integrate_asyncio_with_tkinter(self):
        def run_async_tasks():
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
            self.root.after(10, run_async_tasks)
        logger.info("Integrating asyncio event loop with Tkinter main loop.")
        self.root.after(10, run_async_tasks)

    async def _init_async_services(self):
        self.ai_analysis_service = AIAnalysisService(OPENAI_API_KEY)
        logger.info("AIAnalysisService initialized asynchronously.")

    def _check_api_configs(self):
        if self.ai_analysis_service is None:
            self.root.after(100, self._check_api_configs)
            return
        if not self.ai_analysis_service.is_configured:
            messagebox.showerror(
                "Configuration Error",
                "OpenAI API Key is missing. Please set the environment variable OPENAI_API_KEY."
            )
            logger.critical("Application cannot proceed due to missing API configurations.")
            self.root.destroy()

    def _setup_hotkeys(self):
        for hotkey in HOTKEYS:
            keyboard.add_hotkey(hotkey, lambda: self.loop.create_task(self._run_analysis_workflow()))
            logger.debug(f"Registered hotkey: {hotkey}")

    async def _run_analysis_workflow(self):
        logger.info("Hotkey pressed. Initiating document capture workflow.")
        # self._manage_results_window_visibility(show=False)
        self._update_ui_with_processing_status(True)

        try:
            logger.info("Waiting for user to select screen region...")
            coordinates = await self.loop.run_in_executor(None, self.screenshot_capture.select_region)
            selected_image = None
            if coordinates:
                selected_image = await self.loop.run_in_executor(None, self.screenshot_capture.crop_image, coordinates)

            if selected_image:
                logger.info("Screen region captured. Performing AI analysis...")
                image_bytes = self._convert_pil_to_bytes(selected_image)
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                analysis_result = await self.ai_analysis_service.analyze_mortgage_document(
                    ocr_text="",
                    base64_image=base64_image
                )

                if not analysis_result.document_id or analysis_result.document_id == "Unnamed Document":
                    analysis_result.document_id = f"Document_{len(self.all_analysis_results) + 1}"

                self.all_analysis_results.append(analysis_result)
                logger.info("AI analysis completed. Displaying results.")
                self._update_ui_with_results(update_data=True, error_message=analysis_result.error)
            else:
                logger.info("Screen capture cancelled or failed.")
                self._update_ui_with_results(update_data=False)
        except Exception as e:
            logger.critical(f"An unhandled error occurred in analysis workflow: {e}", exc_info=True)
            error_msg = f"An unexpected error occurred: {e}"
            dummy_result = AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=error_msg, document_id=f"Document_{len(self.all_analysis_results) + 1}_Error")
            self.all_analysis_results.append(dummy_result)
            self._update_ui_with_results(update_data=True, error_message=error_msg)
        finally:
            self._update_ui_with_processing_status(False)

    def _convert_pil_to_bytes(self, pil_image: Image.Image) -> bytes:
        byte_arr = BytesIO()
        pil_image.save(byte_arr, format='PNG')
        return byte_arr.getvalue()

    def _update_ui_with_results(self, update_data: bool, error_message: str = None):
        self.root.after(0, self._manage_results_window_visibility, True, update_data, error_message)

    def _update_ui_with_processing_status(self, processing: bool):
        self.root.after(0, self._manage_results_window_processing_visibility, processing)

    def _manage_results_window_visibility(self, show: bool, update_data: bool = False, error_message: str = None):
        current_results = self.all_analysis_results

        if error_message and not current_results:
            current_results = [AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=error_message)]
            logger.warning(f"Displaying results with error: {error_message}")

        if not self.results_window or not self.results_window.winfo_exists():
            if show:
                logger.info("Creating new ResultsWindow.")
                self.results_window = ResultsWindow(
                    self.root,
                    current_results,
                    self._on_new_input_callback_from_results_ui
                )
                self.results_window._center_window()
        else:
            if show:
                logger.info("Updating existing ResultsWindow.")
                if update_data:
                    self.results_window.update_data(current_results)
                self.results_window.deiconify()
                self.results_window.lift()
                self.results_window.focus_force()
            else:
                self.results_window.withdraw()

    def _manage_results_window_processing_visibility(self, processing: bool):
        if self.results_window and self.results_window.winfo_exists():
            self.results_window.hide_processing_message()
            # if processing:
            #     self.results_window.show_processing_message()
            # else:
            #     self.results_window.hide_processing_message()

    # def _on_new_input_callback_from_results_ui(self):
    #     logger.info("User requested new document capture. Clearing stored results.")
    #     self.all_analysis_results.clear()
    #     self._manage_results_window_visibility(show=True, update_data=True)
    #     self._manage_results_window_visibility(show=False)
    #     logger.info("UI cleared. Waiting for hotkey to initiate new screenshot capture.")

    def _on_new_input_callback_from_results_ui(self):
        logger.info("User requested new document capture. Clearing stored results.")
        self.all_analysis_results.clear()
        self._manage_results_window_visibility(show=True, update_data=True)
        logger.info("UI refreshed and ready for new input.")


    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MortgageDocumentAnalyzerApp()
    app.run()