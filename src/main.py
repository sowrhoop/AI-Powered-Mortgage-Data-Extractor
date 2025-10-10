import os
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
from ui.settings_window import SettingsWindow
from utils.common_utils import get_dpi_scale_factor
from models.document_entities import AnalysisResult, MortgageDocumentEntities

try:
    import ctypes
    try:
        # Prefer per-monitor DPI awareness on Windows 10/11
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.info("Process set to Per-Monitor DPI Aware (v1).")
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()
        logger.info("Process set to System DPI Aware.")
except Exception:
    logger.warning("Failed to set process DPI awareness. High-DPI layouts may be affected.")

class AscendantVisionAIPlatformApp:
    def __init__(self):
        logger.info("Initializing AscendantVisionAIPlatformApp...")
        self.root = tk.Tk()
        self.root.withdraw()

        self.all_analysis_results: List[AnalysisResult] = []
        self.screenshots_taken_count: int = 0
        self.screenshots_processed_count: int = 0
        self.active_hotkey_hooks: List[Any] = []
        self.is_shutting_down = False
        self.status_label: Optional[ttk.Label] = None

        self._load_settings()

        self.dpi_scale_factor = get_dpi_scale_factor()
        logger.info(f"Detected DPI Scale Factor: {self.dpi_scale_factor}")

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
        self._setup_hotkeys()
        logger.info(f"Application initialized. Listening for hotkeys: {', '.join(config.HOTKEYS)}")

        self.loop.create_task(self._init_async_services())
        self.root.after(100, self._check_api_configs)

        self._init_ui_windows()

        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)

    def _load_settings(self):
        try:
            if os.path.exists(config.SETTINGS_FILE_PATH):
                with open(config.SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                config.OPENAI_API_KEY = settings.get('OPENAI_API_KEY', config.OPENAI_API_KEY)
                # Optional settings: model, timeout, UI confidence
                try:
                    config.OPENAI_MODEL = settings.get('OPENAI_MODEL', config.OPENAI_MODEL)
                except Exception:
                    pass
                try:
                    if 'OPENAI_TIMEOUT' in settings:
                        config.OPENAI_TIMEOUT = float(settings.get('OPENAI_TIMEOUT', config.OPENAI_TIMEOUT))
                except Exception:
                    logger.warning("Invalid OPENAI_TIMEOUT in settings; keeping previous value.")
                try:
                    if 'UI_CONFIDENCE_MIN' in settings:
                        config.UI_CONFIDENCE_MIN = float(settings.get('UI_CONFIDENCE_MIN', config.UI_CONFIDENCE_MIN))
                except Exception:
                    logger.warning("Invalid UI_CONFIDENCE_MIN in settings; keeping previous value.")
                
                loaded_hotkeys = settings.get('HOTKEYS')
                if isinstance(loaded_hotkeys, list):
                    config.HOTKEYS = loaded_hotkeys
                else:
                    logger.warning("Hotkeys loaded from settings file were not a list. Using default.")
                    # Use in-app defaults, do not read environment variables
                    config.HOTKEYS = ['ctrl+alt+m', 'ctrl+alt+a']

                logger.info(f"Settings loaded from {config.SETTINGS_FILE_PATH}")
            else:
                logger.info("Settings file not found. Using default configurations.")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding settings JSON from {config.SETTINGS_FILE_PATH}: {e}. Using default configurations.", exc_info=True)
            self._show_status_message(f"Error loading settings: Invalid JSON. Using defaults. ({e})", is_error=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading settings: {e}. Using default configurations.", exc_info=True)
            self._show_status_message(f"Error loading settings: {e}. Using defaults.", is_error=True)

    def _save_settings(self, settings_to_save: dict):
        try:
            os.makedirs(os.path.dirname(config.SETTINGS_FILE_PATH), exist_ok=True)
            with open(config.SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=4, ensure_ascii=False)
            logger.info(f"Settings saved to {config.SETTINGS_FILE_PATH}")
        except Exception as e:
            logger.error(f"Failed to save settings to {config.SETTINGS_FILE_PATH}: {e}", exc_info=True)
            self._show_status_message(f"Failed to save settings: {e}", is_error=True)

    def _integrate_asyncio_with_tkinter(self):
        def run_async_tasks():
            if not self.is_shutting_down:
                self.loop.call_soon(self.loop.stop)
                self.loop.run_forever()
                self.root.after(10, run_async_tasks)
        logger.info("Integrating asyncio event loop with Tkinter main loop.")
        self.root.after(10, run_async_tasks)

    async def _init_async_services(self):
        self.ai_analysis_service = AIAnalysisService(config.OPENAI_API_KEY)
        if self.ai_analysis_service.is_configured:
            logger.info("AIAnalysisService initialized asynchronously.")
        else:
            logger.warning("AIAnalysisService could not be configured due to missing API key. Please check settings.")
            self._show_status_message("AI service not configured. Please set your OpenAI API key.", is_error=True)

    def _check_api_configs(self):
        if self.ai_analysis_service is None:
            self.root.after(100, self._check_api_configs)
            return
        if not self.ai_analysis_service.is_configured:
            if self.results_window and self.results_window.winfo_exists():
                self.results_window.lift()
                self.results_window.focus_force()

            # Automatically prompt for API key at launch if missing
            settings_open = False
            try:
                settings_open = bool(getattr(self, '_settings_dialog', None) and self._settings_dialog.winfo_exists())
            except Exception:
                settings_open = False
            if not settings_open:
                logger.info("OpenAI API key missing. Opening Settings window for user input.")
                self._open_settings_window()

            # Inline status reminder in the UI
            self._show_status_message("Enter your OpenAI API key in Settings.", is_error=True)
        else:
            self._show_status_message("Application ready. Press hotkey to capture.", is_error=False)

    def _setup_hotkeys(self):
        for hook in self.active_hotkey_hooks:
            try:
                keyboard.unhook(hook)
                logger.debug(f"Unhooked old hotkey: {hook}")
            except Exception as e:
                logger.warning(f"Failed to unhook hotkey {hook}: {e}")
        self.active_hotkey_hooks.clear()

        for hotkey in config.HOTKEYS:
            try:
                hook = keyboard.add_hotkey(hotkey, lambda: self.loop.create_task(self._run_analysis_workflow()))
                self.active_hotkey_hooks.append(hook)
                logger.debug(f"Registered hotkey: {hotkey}, Hook: {hook}")
            except Exception as e:
                logger.error(f"Failed to register hotkey '{hotkey}': {e}. This hotkey will not function.", exc_info=True)
                self._show_status_message(f"Failed to register hotkey '{hotkey}'. Check permissions or try a different key.", is_error=True)

    def _init_ui_windows(self):
        dummy_result = AnalysisResult(
            entities=MortgageDocumentEntities(),
            summary="",
            error=None,
            document_id="Document_0"
        )
        if not self.all_analysis_results:
            self.all_analysis_results.append(dummy_result)
        
        logger.info(f"Initializing ResultsWindow with current data: {len(self.all_analysis_results)} results.")
        self.results_window = ResultsWindow(
            self.root,
            self.all_analysis_results,
            on_new_input_callback=self._trigger_new_capture_for_current_session,
            on_close_callback=self._on_results_window_closed
        )
        self.results_window._position_window_on_right_half()
        self.results_window.add_settings_button(self._open_settings_window)
        self.results_window.set_capture_callbacks(
            on_new_capture_callback=self._trigger_new_capture_for_current_session,
            on_start_new_session_callback=self._start_new_session_callback
        )
        self.status_label = ttk.Label(self.results_window, text="", anchor="w", font=("Helvetica", 10))
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self._show_status_message("Application ready. Press hotkey to capture.", is_error=False)

        logger.info("ResultsWindow initialized and ready.")

    async def _run_analysis_workflow(self):
        logger.info("Hotkey pressed. Initiating document capture workflow.")

        if self.is_shutting_down:
            logger.info("Application is shutting down, ignoring new capture request.")
            self._show_status_message("Application is shutting down. Cannot start new capture.", is_error=True)
            return

        if not self.ai_analysis_service or not self.ai_analysis_service.is_configured:
            self._show_status_message("AI analysis service not configured. Please set your OpenAI API key in settings.", is_error=True)
            logger.error("AI analysis service not configured. Aborting workflow.")
            return

        selected_image = None
        placeholder_index: Optional[int] = None
        try:
            self._show_status_message("Waiting for user to select screen region...", is_error=False)
            logger.info("Waiting for user to select screen region...")
            coordinates = await self._select_region_async()

            if coordinates:
                self._show_status_message("Screen region captured. Cropping image...", is_error=False)
                selected_image = await self.loop.run_in_executor(None, self.screenshot_capture.crop_image, coordinates)
                self.screenshots_taken_count += 1

            if selected_image:
                self._show_status_message("Image cropped. Performing AI analysis...", is_error=False)
                logger.info("Screen region captured. Performing AI analysis...")
                image_bytes = self._convert_pil_to_bytes(selected_image)
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                # Append a placeholder entry that will be replaced in-place when analysis completes
                placeholder_result = AnalysisResult(
                    entities=MortgageDocumentEntities(),
                    summary="Processing...",
                    error=None,
                    document_id=f"Document_{len(self.all_analysis_results) + 1}"
                )
                self.all_analysis_results.append(placeholder_result)
                placeholder_index = len(self.all_analysis_results) - 1
                self._update_ui_with_results(update_data=True)

                analysis_result = await self.ai_analysis_service.analyze_mortgage_document(
                    ocr_text="",
                    base64_image=base64_image
                )

                # Normalize/assign a stable document id
                if (not analysis_result.document_id
                    or analysis_result.document_id == "Unnamed Document"
                    or "Document_0" in analysis_result.document_id):
                    analysis_result.document_id = f"Document_{placeholder_index + 1}"

                # Replace placeholder in-place; if for any reason index is invalid, upsert by id
                if placeholder_index is not None and 0 <= placeholder_index < len(self.all_analysis_results):
                    self.all_analysis_results[placeholder_index] = analysis_result
                else:
                    self._upsert_analysis_result(analysis_result)

                # Propagate higher-confidence fields from the new result back into older results
                self._propagate_higher_confidence_to_history(analysis_result.entities, exclude_index=placeholder_index)

                self.screenshots_processed_count += 1
                logger.info(
                    f"AI analysis completed. Total taken: {self.screenshots_taken_count}, "
                    f"Processed: {self.screenshots_processed_count}"
                )
                self._show_status_message("AI analysis completed. Displaying results.", is_error=False)
                self._update_ui_with_results(update_data=True, error_message=analysis_result.error)

            else:
                logger.info("Screen capture cancelled or failed.")
                # If nothing meaningful exists besides initial dummy, clean up for clarity
                if len(self.all_analysis_results) == 1 and self.all_analysis_results[0].document_id == "Document_0":
                    self.all_analysis_results.clear()
                self._update_ui_with_results(update_data=True)
                self._show_status_message("Screen capture cancelled.", is_error=False)

        except Exception as e:
            logger.critical(f"An unhandled error occurred in analysis workflow: {e}", exc_info=True)
            error_msg = f"An unexpected error occurred: {e}"

            error_result = AnalysisResult(
                entities=MortgageDocumentEntities(),
                summary="",
                error=error_msg,
                document_id=f"Document_{len(self.all_analysis_results) + 1}_Error"
            )

            # If the last entry is a placeholder (Processing...), replace it with the error
            if self.all_analysis_results and self.all_analysis_results[-1].summary == "Processing...":
                self.all_analysis_results[-1] = error_result
            else:
                self.all_analysis_results.append(error_result)

            self._update_ui_with_results(update_data=True, error_message=error_msg)
            self._show_status_message(f"Analysis failed: {e}", is_error=True)
        finally:
            if selected_image:
                selected_image.close()

    async def _select_region_async(self):
        """Run region selection on Tk main thread and await result safely."""
        future: asyncio.Future = self.loop.create_future()

        def _do_select():
            try:
                coords = self.screenshot_capture.select_region()
                if not future.done():
                    future.set_result(coords)
            except Exception as e:
                logger.error(f"Error during region selection: {e}", exc_info=True)
                if not future.done():
                    future.set_exception(e)

        # Schedule on Tk main loop
        self.root.after(0, _do_select)
        return await future

    # ------------------------------
    # Results management helpers
    # ------------------------------
    def _upsert_analysis_result(self, new_result: AnalysisResult):
        """Insert or merge result into the list by document_id, keeping highest-confidence values."""
        try:
            existing_idx = next(
                (i for i, r in enumerate(self.all_analysis_results) if r.document_id == new_result.document_id),
                None
            )
        except Exception:
            existing_idx = None

        if existing_idx is None:
            self.all_analysis_results.append(new_result)
            return

        merged = self._merge_entities_keep_highest_confidence(
            self.all_analysis_results[existing_idx].entities,
            new_result.entities
        )
        self.all_analysis_results[existing_idx] = AnalysisResult(
            entities=merged,
            summary=new_result.summary or self.all_analysis_results[existing_idx].summary,
            error=new_result.error,
            document_id=new_result.document_id,
        )

    def _merge_entities_keep_highest_confidence(
        self,
        base: MortgageDocumentEntities,
        new: MortgageDocumentEntities,
    ) -> MortgageDocumentEntities:
        merged = MortgageDocumentEntities()

        # List-like fields that should be unioned
        list_fields = {
            "Borrower",
        }

        def _normalize_string_for_comparison(s: str) -> str:
            try:
                return "".join(ch for ch in str(s).lower() if ch.isalnum())
            except Exception:
                return ""

        def _is_similar_name(existing_norms: set, new_name: str, threshold: float = 0.85) -> bool:
            try:
                import difflib
            except Exception:
                # If difflib unavailable, fallback to exact-match only
                return _normalize_string_for_comparison(new_name) in existing_norms

            norm_new = _normalize_string_for_comparison(new_name)
            if not norm_new:
                return False
            for norm_existing in existing_norms:
                ratio = difflib.SequenceMatcher(None, norm_new, norm_existing).ratio()
                if ratio >= threshold:
                    return True
            return False

        for field_name in merged.__dataclass_fields__.keys():
            base_cv = getattr(base, field_name)
            new_cv = getattr(new, field_name)

            # Riders: union by rider name, keep highest confidence
            if field_name == "RidersPresent":
                base_list = base_cv.value if isinstance(base_cv.value, list) else []
                new_list = new_cv.value if isinstance(new_cv.value, list) else []

                riders_by_name = {}
                for r in (base_list + new_list):
                    try:
                        name = getattr(r.Name, "value", None) if r else None
                        name_conf = getattr(r.Name, "confidence", 0.0) if r else 0.0
                        if not name:
                            continue
                        if name not in riders_by_name or name_conf > getattr(riders_by_name[name].Name, "confidence", 0.0):
                            riders_by_name[name] = r
                    except Exception:
                        continue

                combined = list(riders_by_name.values())
                confidence = max(base_cv.confidence, new_cv.confidence)
                setattr(merged, field_name, type(base_cv)(value=combined, confidence=confidence))
                continue

            # Borrower: union by Name, merge alias lists, keep higher-confidence relationship/tenant
            if field_name == "Borrower":
                base_list = base_cv.value if isinstance(base_cv.value, list) else []
                new_list = new_cv.value if isinstance(new_cv.value, list) else []

                borrowers_by_key = {}
                def _norm(s):
                    try:
                        return "".join(ch for ch in str(s).lower() if ch.isalnum())
                    except Exception:
                        return ""
                for b in (base_list + new_list):
                    try:
                        name_val = getattr(b.Name, "value", None) if b else None
                        name_conf = getattr(b.Name, "confidence", 0.0) if b else 0.0
                        key = _norm(name_val)
                        if not key:
                            continue
                        if key not in borrowers_by_key or name_conf > getattr(borrowers_by_key[key].Name, "confidence", 0.0):
                            borrowers_by_key[key] = b
                        else:
                            existing = borrowers_by_key[key]
                            # Merge alias lists
                            try:
                                a1 = existing.Alias.value if isinstance(existing.Alias.value, list) else []
                                a2 = b.Alias.value if isinstance(b.Alias.value, list) else []
                                union = list(dict.fromkeys([str(x).strip() for x in a1 + a2 if str(x).strip()]))
                                existing.Alias.value = union
                                existing.Alias.confidence = max(existing.Alias.confidence or 0.0, b.Alias.confidence or 0.0)
                            except Exception:
                                pass
                            # Relationship/TenantInformation by higher confidence
                            try:
                                if (b.Relationship.confidence or 0.0) > (existing.Relationship.confidence or 0.0):
                                    existing.Relationship = b.Relationship
                            except Exception:
                                pass
                            try:
                                if (b.TenantInformation.confidence or 0.0) > (existing.TenantInformation.confidence or 0.0):
                                    existing.TenantInformation = b.TenantInformation
                            except Exception:
                                pass
                    except Exception:
                        continue

                combined = list(borrowers_by_key.values())
                confidence = max(base_cv.confidence, new_cv.confidence)
                setattr(merged, field_name, type(base_cv)(value=combined, confidence=confidence))
                continue

            # Scalar fields: pick higher-confidence valid value; fallback to the other
            if (new_cv.confidence > base_cv.confidence and self._is_valid_value(new_cv.value)) or not self._is_valid_value(base_cv.value):
                chosen = new_cv
            else:
                chosen = base_cv
            setattr(merged, field_name, chosen)

        # Harmonize LegalDescriptionPresent with LegalDescriptionDetail
        try:
            legal_detail = merged.LegalDescriptionDetail
            legal_present = merged.LegalDescriptionPresent
            if str(getattr(legal_detail, "value", "")).strip() and str(getattr(legal_detail, "value", "")).strip().lower() not in {"n/a", "not listed", "legal description is missing"}:
                legal_present.value = "Yes"
                legal_present.confidence = max(legal_present.confidence, legal_detail.confidence)
            else:
                if legal_present.value not in {"No", "N/A"}:
                    legal_present.value = "No"
                legal_present.confidence = max(legal_present.confidence, legal_detail.confidence)
        except Exception:
            pass

        return merged

    @staticmethod
    def _is_valid_value(val: Any) -> bool:
        if val is None:
            return False
        if isinstance(val, str):
            normalized_val = val.strip().lower()
            return normalized_val not in ["n/a", "not listed", "", "legal description is missing"] and val.strip() != "No"
        if isinstance(val, list):
            return bool(val)
        if isinstance(val, dict):
            return bool(val)
        return True

    def _propagate_higher_confidence_to_history(
        self,
        source_entities: MortgageDocumentEntities,
        exclude_index: Optional[int] = None,
    ) -> None:
        """
        Update older results so that any field with a lower confidence is upgraded
        to the value from source_entities. This preserves history entries while
        ensuring they reflect the strongest known values field-by-field.
        """
        try:
            for idx, result in enumerate(self.all_analysis_results):
                if exclude_index is not None and idx == exclude_index:
                    continue
                if result.error or not result.entities:
                    continue
                merged = self._merge_entities_keep_highest_confidence(result.entities, source_entities)
                result.entities = merged
        except Exception as e:
            logger.warning(f"Failed to propagate higher-confidence entities to history: {e}")

    def _convert_pil_to_bytes(self, pil_image: Image.Image, dpi : int = 300) -> bytes:
        byte_arr = BytesIO()
        pil_image.save(byte_arr, format='PNG', dpi=(dpi, dpi))
        return byte_arr.getvalue()

    def _update_ui_with_results(self, update_data: bool, error_message: str = None):
        self.root.after(0, self._manage_results_window_visibility, True, update_data, error_message)

    def _manage_results_window_visibility(self, show: bool, update_data: bool = False, error_message: str = None):
        current_results = self.all_analysis_results

        if error_message and not current_results:
            current_results = [AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=error_message, document_id="Error_Doc")]
            logger.warning(f"Displaying results with error: {error_message}")
        
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
                self.status_label = ttk.Label(self.results_window, text="", anchor="w", font=("Helvetica", 10))
                self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
                self.results_window.lift()
                self.results_window.focus_force()
            else:
                # No-op: window already hidden
                return
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

    def _trigger_new_capture_for_current_session(self):
        logger.info("User requested new document capture for current session.")
        if self.results_window:
            self.results_window.deiconify()
            self.results_window.lift()
            self.results_window.focus_force()
        
        self.loop.create_task(self._run_analysis_workflow())

    def _start_new_session_callback(self):
        logger.info("User requested to start a new session. Clearing all stored results.")
        self.all_analysis_results.clear()
        self.screenshots_taken_count = 0
        self.screenshots_processed_count = 0
        self.all_analysis_results.append(AnalysisResult(
            entities=MortgageDocumentEntities(),
            summary="",
            error=None,
            document_id="Document_0"
        ))
        self._manage_results_window_visibility(show=True, update_data=True)
        self._show_status_message("New session started. Ready for capture.", is_error=False)
        logger.info("UI refreshed and ready for new input.")

    def _open_settings_window(self):
        logger.info("Opening settings window.")
        current_settings = {
            'OPENAI_API_KEY': config.OPENAI_API_KEY,
            'HOTKEYS': config.HOTKEYS,
            'OPENAI_MODEL': getattr(config, 'OPENAI_MODEL', ''),
            'OPENAI_TIMEOUT': getattr(config, 'OPENAI_TIMEOUT', ''),
            'UI_CONFIDENCE_MIN': getattr(config, 'UI_CONFIDENCE_MIN', '')
        }
        # Reuse existing settings dialog if it's already open
        existing = getattr(self, "_settings_dialog", None)
        if existing and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        
        self._settings_dialog = SettingsWindow(self.root, current_settings, self._apply_settings)
        self._settings_dialog.focus_set()
        self._settings_dialog.grab_set()

    def _apply_settings(self, new_settings: dict):
        logger.info(f"Applying new settings: {new_settings}")
        
        if config.OPENAI_API_KEY != new_settings['OPENAI_API_KEY']:
            config.OPENAI_API_KEY = new_settings['OPENAI_API_KEY']
            logger.info("OpenAI API key changed. Re-initializing AIAnalysisService.")
            self.loop.create_task(self._init_async_services())
            self.root.after(500, self._check_api_configs) 
        else:
            logger.info("OpenAI API key did not change.")

        # Update other config values
        try:
            model_changed = getattr(config, 'OPENAI_MODEL', None) != new_settings.get('OPENAI_MODEL')
            config.OPENAI_MODEL = new_settings.get('OPENAI_MODEL', config.OPENAI_MODEL)
            if model_changed:
                logger.info(f"OpenAI model changed to {config.OPENAI_MODEL}.")
        except Exception:
            logger.warning("Failed to update OPENAI_MODEL from settings.")

        try:
            timeout_val = float(new_settings.get('OPENAI_TIMEOUT', config.OPENAI_TIMEOUT))
            timeout_changed = getattr(config, 'OPENAI_TIMEOUT', None) != timeout_val
            config.OPENAI_TIMEOUT = timeout_val
            if timeout_changed:
                logger.info(f"OpenAI timeout changed to {config.OPENAI_TIMEOUT} seconds.")
        except Exception:
            logger.warning("Failed to update OPENAI_TIMEOUT from settings.")

        try:
            ui_conf_val = float(new_settings.get('UI_CONFIDENCE_MIN', config.UI_CONFIDENCE_MIN))
            ui_conf_changed = getattr(config, 'UI_CONFIDENCE_MIN', None) != ui_conf_val
            config.UI_CONFIDENCE_MIN = ui_conf_val
            if ui_conf_changed:
                logger.info(f"UI confidence threshold changed to {config.UI_CONFIDENCE_MIN}.")
        except Exception:
            logger.warning("Failed to update UI_CONFIDENCE_MIN from settings.")

        self._save_settings(new_settings)
        # Refresh the UI to reflect any updated thresholds/configs
        self._update_ui_with_results(update_data=True)

    def _on_results_window_closed(self):
        logger.info("Results window closed. Initiating application shutdown.")
        self.is_shutting_down = True
        self.root.quit()

    def on_app_close(self):
        logger.info("Main application root window closing (via root window close protocol).")
        self.is_shutting_down = True
        self.root.quit()

    def _show_status_message(self, message: str, is_error: bool = False):
        if self.status_label and self.status_label.winfo_exists():
            self.status_label.config(text=message, foreground="red" if is_error else "black")
            logger.info(f"UI Status: {message}")
        else:
            logger.warning(f"Status label not available to display message: {message}")

    def run(self):
        self.root.mainloop()
        logger.info("Tkinter main loop exited. Closing asyncio loop.")
        if not self.loop.is_closed():
            self.loop.close()
        logger.info("Application shut down.")

if __name__ == "__main__":
    app = AscendantVisionAIPlatformApp()
    app.run()