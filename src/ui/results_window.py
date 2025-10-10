import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Callable, Any, List, Dict, Optional
from models.document_entities import AnalysisResult, MortgageDocumentEntities, Rider, ConfidenceValue, BorrowerEntry
from dataclasses import fields
import re
import difflib
import config
from utils.common_utils import get_work_area

logger = logging.getLogger(__name__)

class ResultsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, all_analysis_results: List[AnalysisResult],
                 on_new_input_callback: Callable[[], None], on_close_callback: Callable[[], None]):
        super().__init__(parent)
        logger.info("ResultsWindow: Initializing...")
        self.title("Ascendant Vision AI Platform")
        self.geometry("850x750")
        self.minsize(600, 500)

        title_label = ttk.Label(
            self,
            text="Ascendant Vision AI Platform",
            font=("Helvetica", 15, "bold"),
            anchor="center"
        )
        title_label.pack(pady=10)

        self._position_window_on_right_half()

        self.all_analysis_results = all_analysis_results
        self.on_new_capture_callback: Optional[Callable[[], None]] = on_new_input_callback
        self.on_start_new_session_callback: Optional[Callable[[], None]] = None
        self.on_close_callback = on_close_callback

        self.entity_entries: Dict[str, tk.Entry] = {}
        self.combined_entities: MortgageDocumentEntities = MortgageDocumentEntities() 
        self.legal_description_detail_text_widget: Optional[tk.Text] = None
        self.error_labels: List[ttk.Label] = []

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.attributes("-topmost", True)
        self.update_idletasks()
        self._position_window_on_right_half()

        self._create_widgets_layout()
        self._populate_content(self.all_analysis_results) 
        logger.info("ResultsWindow: Widgets created and content populated.")

        self.lift()
        self.focus_force()
        self.update()
        logger.info("Results window created and displayed (attempted to bring to front and focus).")

    @staticmethod
    def _format_currency_str(s: Any) -> Optional[str]:
        try:
            txt = str(s)
        except Exception:
            return None
        cleaned = re.sub(r"[$,\s]", "", txt)
        if not cleaned:
            return None
        try:
            val = float(cleaned)
            return f"{val:.2f}"
        except Exception:
            return None

    def _position_window_on_right_half(self):
        self.update_idletasks()
        try:
            left, top, right, bottom = get_work_area()
            work_w = max(0, right - left)
            work_h = max(0, bottom - top)
            # Aim for right half of the working area, clamped to min size but not exceeding work area
            target_w = max(min(work_w // 2, work_w), 600)
            target_w = min(target_w, work_w)
            target_h = work_h  # use full height of working area for visibility
            x = left + (work_w - target_w)
            y = top
            geom = f"{int(target_w)}x{int(target_h)}+{int(x)}+{int(y)}"
            self.geometry(geom)
            logger.debug(f"ResultsWindow: Snapped to right half using work area [{geom}] (work {work_w}x{work_h} @ {left},{top})")
        except Exception as e:
            logger.warning(f"Failed to position on right half via work area: {e}. Falling back to screen metrics.")
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            width = max(600, screen_width // 2)
            height = screen_height
            x = screen_width // 2
            y = 0
            self.geometry(f"{width}x{height}+{x}+{y}")

    def _create_widgets_layout(self):
        main_content_frame = ttk.Frame(self, padding="10")
        main_content_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        self.entities_grid_container = ttk.Frame(main_content_frame)
        self.entities_grid_container.pack(expand=True, fill=tk.BOTH)

        self.entities_grid_container.grid_columnconfigure(0, weight=0)
        self.entities_grid_container.grid_columnconfigure(1, weight=1)
        self.entities_grid_container.grid_columnconfigure(2, weight=0)
        self.entities_grid_container.grid_columnconfigure(3, weight=0)
        self.entities_grid_container.grid_columnconfigure(4, weight=1)
        self.entities_grid_container.grid_columnconfigure(5, weight=0)

        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(pady=10)
        
        self.save_button = ttk.Button(self.button_frame, text="Save Edits", command=self._save_edits_to_global_entities)
        self.save_button.pack(side=tk.LEFT, padx=5)

        self.start_new_session_btn = ttk.Button(self.button_frame, text="Start New Session", command=self._on_start_new_session_clicked)
        self.start_new_session_btn.pack(side=tk.LEFT, padx=5)


    def set_capture_callbacks(self, on_new_capture_callback: Callable[[], None], on_start_new_session_callback: Callable[[], None]):
        self.on_new_capture_callback = on_new_capture_callback
        self.on_start_new_session_callback = on_start_new_session_callback
        self.start_new_session_btn.config(command=self._on_start_new_session_clicked)
        logger.info("ResultsWindow: Capture callbacks set.")

    def add_settings_button(self, command: Callable):
        self.settings_button = ttk.Button(self.button_frame, text="Settings", command=command)
        self.settings_button.pack(side=tk.RIGHT, padx=5)

    def _flash_button(self, btn: ttk.Button, flash_text: str = "Done ✓", duration_ms: int = 1200, restore_text: Optional[str] = None):
        try:
            if not btn or not btn.winfo_exists():
                return
            original = restore_text if restore_text is not None else btn["text"]
            btn.config(text=flash_text)
            btn.state(["disabled"])  # temporarily disable to avoid double clicks
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

    def _normalize_string_for_comparison(self, s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', s.lower())

    def _split_borrower_names(self, text: str) -> List[str]:
        try:
            raw = str(text)
        except Exception:
            return []
        # Take portion before first comma to avoid trailing relationship/tenant info
        head = raw.split(',', 1)[0]
        # Split on common connectors 'and' / '&'
        parts = re.split(r"\s*(?:&|and)\s*", head, flags=re.IGNORECASE)
        # Clean labels like 'Borrower', 'Mortgagor', etc.
        cleaned = []
        for p in parts:
            c = p.strip()
            for label in ["Borrower", "Mortgagor", "Owner", "Trustor"]:
                if c.lower().startswith(label.lower()):
                    c = c[len(label):].strip(" ,:")
            if c:
                cleaned.append(c)
        return cleaned

    def is_similar_name(self, existing_names: set, new_name: str, threshold: float = 0.85) -> bool:
        norm_new_name = self._normalize_string_for_comparison(new_name)
        if not norm_new_name:
            return False

        for existing_name in existing_names:
            norm_existing_name = self._normalize_string_for_comparison(existing_name)
            if not norm_existing_name:
                continue

            s = difflib.SequenceMatcher(None, norm_new_name, norm_existing_name)
            if s.ratio() >= threshold:
                logger.debug(f"Found similar name: '{new_name}' (normalized '{norm_new_name}') is similar to '{existing_name}' (normalized '{norm_existing_name}') with ratio {s.ratio():.2f}")
                return True
        return False

    def _clear_grid_widgets(self):
        for widget in self.entities_grid_container.winfo_children():
            widget.destroy()
        self.entity_entries.clear()
        for label in self.error_labels:
            if label.winfo_exists():
                label.destroy()
        self.error_labels.clear()

    def _get_underlying_value(self, value: Any) -> Any:
        """Helper to get the actual value from a ConfidenceValue object or return the value itself."""
        return value.value if isinstance(value, ConfidenceValue) else value

    def _is_value_valid(self, value: Any) -> bool:
        val = self._get_underlying_value(value) # Use helper to get the actual value

        if val is None:
            return False
        if isinstance(val, str):
            normalized_val = val.strip().lower()
            return normalized_val not in ["n/a", "not listed", "legal description is missing", ""] and val.strip() != "No"
        if isinstance(val, list):
            return bool(val)
        if isinstance(val, dict):
            return bool(val)
        return True

    def _canonicalize_rider_name(self, name: str) -> Optional[str]:
        if not isinstance(name, str):
            return None
        raw = name.strip()
        if not raw:
            return None
        # Normalize whitespace and punctuation for lookup
        lowered = re.sub(r"\s+", " ", re.sub(r"[\u2010-\u2015]", "-", raw)).strip().lower()
        canon = config.RIDER_ALIASES.get(lowered)
        # If alias returns empty string or None, treat as unsupported
        if canon is None:
            # If not explicitly in aliases, try direct match against allowlist (case-insensitive)
            for allowed in config.RIDER_ALLOWLIST:
                if lowered == allowed.lower():
                    canon = allowed
                    break
        if canon == "":
            return None
        return canon

    def _combine_analysis_results(self, all_results: List[AnalysisResult]) -> MortgageDocumentEntities:
        """
        Combines multiple AnalysisResults into a single MortgageDocumentEntities instance,
        prioritizing values with higher confidence scores and enforcing the
        high-confidence system for updates/appends. For multi-part fields like
        Legal Description, high-confidence segments are concatenated in capture
        order.
        """
        combined_entities = MortgageDocumentEntities()

        # If no actual analysis results, return default empty entities
        if not any(result for result in all_results if not result.error and result.entities):
            return combined_entities

        threshold = float(getattr(config, 'UI_CONFIDENCE_MIN', 0.9) or 0.9)

        # Pre-collect Legal Description high-confidence segments to concatenate
        legal_segments: List[str] = []
        legal_segments_conf: List[float] = []
        for res in all_results:
            if res.error or not res.entities:
                continue
            try:
                detail_cv: ConfidenceValue = getattr(res.entities, 'LegalDescriptionDetail', ConfidenceValue(value='N/A'))
                val = self._get_underlying_value(detail_cv)
                conf = float(getattr(detail_cv, 'confidence', 0.0) or 0.0)
                if self._is_value_valid(val) and conf >= threshold:
                    # Deduplicate by normalized text while preserving original text
                    norm = re.sub(r"\s+", " ", str(val)).strip().lower()
                    if norm and all(re.sub(r"\s+", " ", s).strip().lower() != norm for s in legal_segments):
                        legal_segments.append(str(val))
                        legal_segments_conf.append(conf)
            except Exception:
                continue

        # Iterate through each field in MortgageDocumentEntities
        for field_info in fields(MortgageDocumentEntities):
            field_name = field_info.name
            
            # Special handling for Borrower (list of BorrowerEntry)
            if field_name == "Borrower":
                combined_borrowers: Dict[str, BorrowerEntry] = {}
                combined_conf = 0.0

                for result in all_results:
                    if result.error or not result.entities:
                        continue
                    current_cv: ConfidenceValue = getattr(result.entities, field_name, ConfidenceValue(value=[]))
                    if isinstance(current_cv.value, list):
                        for b in current_cv.value:
                            if not isinstance(b, BorrowerEntry):
                                continue
                            name_val = self._get_underlying_value(b.Name)
                            if not self._is_value_valid(name_val):
                                continue
                            # Enforce high-confidence for borrower Name
                            try:
                                name_conf_val = float(self._get_underlying_value(b.Name.confidence) or 0.0)
                            except Exception:
                                name_conf_val = 0.0
                            if name_conf_val < threshold:
                                continue
                            key = self._normalize_string_for_comparison(name_val)
                            if not key:
                                continue
                            if key not in combined_borrowers or self._get_underlying_value(b.Name.confidence) > self._get_underlying_value(combined_borrowers[key].Name.confidence):
                                # When adopting a borrower, clear low-confidence subfields
                                try:
                                    a_conf = float(self._get_underlying_value(b.Alias.confidence) or 0.0)
                                    if a_conf < threshold:
                                        b.Alias.value = []
                                        b.Alias.confidence = a_conf
                                except Exception:
                                    pass
                                try:
                                    r_conf = float(self._get_underlying_value(b.Relationship.confidence) or 0.0)
                                    if r_conf < threshold:
                                        b.Relationship.value = "N/A"
                                        b.Relationship.confidence = r_conf
                                except Exception:
                                    pass
                                try:
                                    t_conf = float(self._get_underlying_value(b.TenantInformation.confidence) or 0.0)
                                    if t_conf < threshold:
                                        b.TenantInformation.value = "N/A"
                                        b.TenantInformation.confidence = t_conf
                                except Exception:
                                    pass
                                combined_borrowers[key] = b
                            else:
                                existing = combined_borrowers[key]
                                # Merge alias lists (only when new alias list is high-confidence)
                                try:
                                    a1 = existing.Alias.value if isinstance(existing.Alias.value, list) else []
                                    a2 = b.Alias.value if isinstance(b.Alias.value, list) else []
                                    union = list(dict.fromkeys([str(x).strip() for x in a1 + a2 if str(x).strip()]))
                                    b_alias_conf = float(self._get_underlying_value(b.Alias.confidence) or 0.0)
                                    if b_alias_conf >= threshold:
                                        existing.Alias.value = union
                                        existing.Alias.confidence = max(self._get_underlying_value(existing.Alias.confidence), b_alias_conf)
                                except Exception:
                                    pass
                                # Relationship/Tenant information keep higher confidence (only if new meets threshold)
                                try:
                                    b_rel_conf = float(self._get_underlying_value(b.Relationship.confidence) or 0.0)
                                    if b_rel_conf >= threshold and b_rel_conf > self._get_underlying_value(existing.Relationship.confidence):
                                        existing.Relationship = b.Relationship
                                except Exception:
                                    pass
                                try:
                                    b_ten_conf = float(self._get_underlying_value(b.TenantInformation.confidence) or 0.0)
                                    if b_ten_conf >= threshold and b_ten_conf > self._get_underlying_value(existing.TenantInformation.confidence):
                                        existing.TenantInformation = b.TenantInformation
                                except Exception:
                                    pass
                    if current_cv.confidence > combined_conf:
                        combined_conf = current_cv.confidence

                if combined_borrowers:
                    sorted_vals = [combined_borrowers[k] for k in sorted(combined_borrowers.keys())]
                    setattr(combined_entities, field_name, ConfidenceValue(value=sorted_vals, confidence=combined_conf))

            # Special handling for RidersPresent (list of Rider objects)
            elif field_name == "RidersPresent":
                combined_riders: Dict[str, Rider] = {} # key: canonical rider name
                combined_riders_confidence = 0.0 # Confidence for the list as a whole

                for result in all_results:
                    if result.error or not result.entities:
                        continue
                    current_cv: ConfidenceValue = getattr(result.entities, field_name, ConfidenceValue(value=[]))
                    if isinstance(current_cv.value, list): # current_cv.value is expected to be list of Rider objects
                        for rider_obj in current_cv.value:
                            # Include only riders that are signed (SignedAttached == "Yes") per business rule
                            is_signed = False
                            try:
                                signed_val = self._get_underlying_value(rider_obj.SignedAttached)
                                is_signed = isinstance(signed_val, str) and signed_val.strip().lower() == "yes"
                            except Exception:
                                is_signed = False

                            # Enforce high confidence on rider Name
                            name_conf_val = 0.0
                            try:
                                name_conf_val = float(self._get_underlying_value(rider_obj.Name.confidence) or 0.0)
                            except Exception:
                                name_conf_val = 0.0

                            if is_signed and name_conf_val >= threshold and isinstance(rider_obj, Rider) and self._is_value_valid(rider_obj.Name.value):
                                raw_name = self._get_underlying_value(rider_obj.Name)
                                canon_name = self._canonicalize_rider_name(raw_name)
                                if not canon_name or canon_name not in config.RIDER_ALLOWLIST:
                                    continue  # guardrail: skip unknown/ambiguous riders
                                candidate = Rider(
                                    Name=ConfidenceValue(value=canon_name, confidence=self._get_underlying_value(rider_obj.Name.confidence)),
                                    Present=rider_obj.Present,
                                    SignedAttached=rider_obj.SignedAttached,
                                )
                                if canon_name not in combined_riders or \
                                   self._get_underlying_value(candidate.Name.confidence) > self._get_underlying_value(combined_riders[canon_name].Name.confidence):
                                    combined_riders[canon_name] = candidate
                        
                        if current_cv.confidence > combined_riders_confidence:
                            combined_riders_confidence = current_cv.confidence
                
                if combined_riders:
                    sorted_riders = [combined_riders[k] for k in sorted(combined_riders.keys())]
                    setattr(combined_entities, field_name, ConfidenceValue(value=sorted_riders, confidence=combined_riders_confidence))

            # Special handling for Legal Description: assign concatenated high-confidence segments
            elif field_name == "LegalDescriptionDetail":
                if legal_segments:
                    concatenated = "\n\n".join(legal_segments)
                    combined_conf = max(legal_segments_conf) if legal_segments_conf else 0.0
                    setattr(combined_entities, 'LegalDescriptionDetail', ConfidenceValue(value=concatenated, confidence=combined_conf))
                continue
            elif field_name == "LegalDescriptionPresent":
                # Skip direct combine here; handled after we decide detail
                continue

            # General handling for all other ConfidenceValue fields
            else:
                best_value: ConfidenceValue = getattr(combined_entities, field_name)
                
                for result in all_results:
                    if result.error or not result.entities:
                        continue
                    
                    current_cv: ConfidenceValue = getattr(result.entities, field_name, ConfidenceValue())

                    # Only consider updates that meet the high-confidence threshold
                    try:
                        conf_val = float(getattr(current_cv, 'confidence', 0.0) or 0.0)
                    except Exception:
                        conf_val = 0.0

                    if not self._is_value_valid(current_cv.value) or conf_val < threshold:
                        continue

                    # Prioritize valid values with higher confidence (both meeting threshold)
                    if (not self._is_value_valid(best_value.value)) or conf_val > float(getattr(best_value, 'confidence', 0.0) or 0.0):
                        best_value = current_cv

                # Only set if best_value meets threshold and is valid; else leave default (N/A)
                try:
                    best_conf = float(getattr(best_value, 'confidence', 0.0) or 0.0)
                except Exception:
                    best_conf = 0.0
                if self._is_value_valid(best_value.value) and best_conf >= threshold:
                    setattr(combined_entities, field_name, best_value)

        # Post-processing for LegalDescriptionPresent based on LegalDescriptionDetail (high-confidence only)
        if legal_segments:
            ld_conf = max(legal_segments_conf) if legal_segments_conf else 0.0
            setattr(combined_entities, 'LegalDescriptionPresent', ConfidenceValue(value='Yes', confidence=ld_conf))
        else:
            setattr(combined_entities, 'LegalDescriptionPresent', ConfidenceValue(value='No', confidence=0.0))

        return combined_entities


    def _display_entity_fields(self, entities_to_display: MortgageDocumentEntities):
        row_idx = 0
        current_col_pair = 0

        all_display_fields = []
        for field_info in fields(MortgageDocumentEntities):
            field_name = field_info.name
            if field_name not in ["LegalDescriptionPresent", "LegalDescriptionDetail"]:
                cv: ConfidenceValue = getattr(entities_to_display, field_name)
                # RidersPresent: only include if at least one rider is signed and the rider name meets confidence threshold
                if field_name == "RidersPresent":
                    signed_count = 0
                    if isinstance(cv.value, list):
                        for r in cv.value:
                            if isinstance(r, Rider) and self._is_value_valid(r.Name.value):
                                signed_val = self._get_underlying_value(r.SignedAttached)
                                try:
                                    name_conf_ok = (float(getattr(r.Name, "confidence", 0.0) or 0.0) >= config.UI_CONFIDENCE_MIN)
                                except Exception:
                                    name_conf_ok = False
                                if isinstance(signed_val, str) and signed_val.strip().lower() == "yes" and name_conf_ok:
                                    signed_count += 1

                    # Fallback detection: if no canonical riders made it into the combined view,
                    # check raw results for any signed, high-confidence riders that are unclassified.
                    fallback_unclassified_signed = 0
                    if signed_count == 0 and isinstance(self.all_analysis_results, list):
                        try:
                            for res in self.all_analysis_results:
                                if getattr(res, 'error', None) or not getattr(res, 'entities', None):
                                    continue
                                rp_cv = getattr(res.entities, 'RidersPresent', ConfidenceValue(value=[]))
                                if isinstance(rp_cv.value, list):
                                    for r in rp_cv.value:
                                        try:
                                            if not isinstance(r, Rider):
                                                continue
                                            raw_name = self._get_underlying_value(r.Name)
                                            if not self._is_value_valid(raw_name):
                                                continue
                                            name_conf = float(getattr(r.Name, 'confidence', 0.0) or 0.0)
                                            signed_val = self._get_underlying_value(r.SignedAttached)
                                            is_signed = isinstance(signed_val, str) and signed_val.strip().lower() == 'yes'
                                            if name_conf >= config.UI_CONFIDENCE_MIN and is_signed:
                                                canon = self._canonicalize_rider_name(raw_name)
                                                if not canon or canon not in getattr(config, 'RIDER_ALLOWLIST', []):
                                                    fallback_unclassified_signed += 1
                                        except Exception:
                                            continue
                        except Exception:
                            pass

                    if signed_count > 0 or fallback_unclassified_signed > 0:
                        all_display_fields.append((field_name, cv))
                    # Move to next field after deciding inclusion
                    continue

                # Borrower: include if at least one entry's Name meets threshold
                if field_name == "Borrower":
                    qualifying = 0
                    if isinstance(cv.value, list):
                        for b in cv.value:
                            try:
                                if isinstance(b, BorrowerEntry):
                                    if float(self._get_underlying_value(b.Name.confidence) or 0.0) >= config.UI_CONFIDENCE_MIN and self._is_value_valid(self._get_underlying_value(b.Name)):
                                        qualifying += 1
                            except Exception:
                                continue
                    if qualifying > 0:
                        all_display_fields.append((field_name, cv))
                    continue

                # Only display values that are valid and meet the confidence threshold
                if self._is_value_valid(cv.value) and float(cv.confidence or 0.0) >= config.UI_CONFIDENCE_MIN:
                    all_display_fields.append((field_name, cv))
        
        all_display_fields.sort(key=lambda item: item[0])

        for key, cv_value in all_display_fields:
            value_str = ""
            if key == "RidersPresent":
                if isinstance(cv_value.value, list):
                    # Display only riders that are signed; present as comma-separated list
                    signed_names: List[str] = []
                    # 1) Canonical, allowlisted riders
                    for r in cv_value.value:
                        if isinstance(r, Rider) and self._is_value_valid(r.Name.value):
                            signed_val = self._get_underlying_value(r.SignedAttached)
                            try:
                                name_conf_ok = (float(getattr(r.Name, "confidence", 0.0) or 0.0) >= config.UI_CONFIDENCE_MIN)
                            except Exception:
                                name_conf_ok = False
                            if isinstance(signed_val, str) and signed_val.strip().lower() == "yes" and name_conf_ok:
                                canon = self._canonicalize_rider_name(self._get_underlying_value(r.Name))
                                if canon and canon in config.RIDER_ALLOWLIST:
                                    signed_names.append(canon)

                    # 2) Fallback: include signed, high-confidence unclassified riders from raw results
                    try:
                        unclassified_names: List[str] = []
                        for res in getattr(self, 'all_analysis_results', []) or []:
                            if getattr(res, 'error', None) or not getattr(res, 'entities', None):
                                continue
                            rp_cv = getattr(res.entities, 'RidersPresent', ConfidenceValue(value=[]))
                            if isinstance(rp_cv.value, list):
                                for r in rp_cv.value:
                                    if not isinstance(r, Rider):
                                        continue
                                    raw_name = self._get_underlying_value(r.Name)
                                    if not self._is_value_valid(raw_name):
                                        continue
                                    try:
                                        name_conf = float(getattr(r.Name, 'confidence', 0.0) or 0.0)
                                    except Exception:
                                        name_conf = 0.0
                                    signed_val = self._get_underlying_value(r.SignedAttached)
                                    is_signed = isinstance(signed_val, str) and signed_val.strip().lower() == 'yes'
                                    if name_conf >= config.UI_CONFIDENCE_MIN and is_signed:
                                        canon = self._canonicalize_rider_name(raw_name)
                                        if not canon or canon not in getattr(config, 'RIDER_ALLOWLIST', []):
                                            unclassified_names.append(str(raw_name))
                        # Merge canonical and unclassified, unique + sorted
                        merged = list(dict.fromkeys(signed_names + unclassified_names))
                        value_str = ", ".join(sorted(merged))
                    except Exception:
                        # Fallback to canonical only if any error occurs
                        value_str = ", ".join(sorted(dict.fromkeys(signed_names)))
                else:
                    # If not a proper list, do not display Riders
                    value_str = ""
            elif key == "Borrower":
                if isinstance(cv_value.value, list):
                    items: List[str] = []
                    for b in cv_value.value:
                        if not isinstance(b, BorrowerEntry):
                            continue
                        name = self._get_underlying_value(b.Name)
                        try:
                            name = str(name).upper()
                        except Exception:
                            pass
                        if not self._is_value_valid(name):
                            continue
                        # Enforce confidence threshold at item level by Name confidence
                        try:
                            name_conf_ok = float(self._get_underlying_value(b.Name.confidence) or 0.0) >= config.UI_CONFIDENCE_MIN
                        except Exception:
                            name_conf_ok = False
                        if not name_conf_ok:
                            continue
                        parts = [name]
                        try:
                            alias_conf_ok = float(self._get_underlying_value(b.Alias.confidence) or 0.0) >= config.UI_CONFIDENCE_MIN
                        except Exception:
                            alias_conf_ok = False
                        try:
                            aliases = b.Alias.value if isinstance(b.Alias.value, list) else []
                            alias_str = ", ".join([str(a) for a in aliases if self._is_value_valid(a)])
                            if alias_str and alias_conf_ok:
                                parts.append(alias_str)
                        except Exception:
                            pass
                        try:
                            rel = self._get_underlying_value(b.Relationship)
                            try:
                                rel = str(rel).upper()
                            except Exception:
                                pass
                            rel_conf_ok = float(self._get_underlying_value(b.Relationship.confidence) or 0.0) >= config.UI_CONFIDENCE_MIN
                            if self._is_value_valid(rel) and rel_conf_ok:
                                parts.append(rel)
                        except Exception:
                            pass
                        try:
                            ten = self._get_underlying_value(b.TenantInformation)
                            try:
                                ten = str(ten).upper()
                            except Exception:
                                pass
                            ten_conf_ok = float(self._get_underlying_value(b.TenantInformation.confidence) or 0.0) >= config.UI_CONFIDENCE_MIN
                            if self._is_value_valid(ten) and ten_conf_ok:
                                parts.append(ten)
                        except Exception:
                            pass
                        items.append("; ".join(parts))
                    value_str = ", ".join(items)
            else: 
                value_str = self._get_underlying_value(cv_value) # Use helper here

            money_fields = tuple(getattr(config, 'MONEY_FIELDS', ["LoanAmount", "RecordingCost"]))
            if key in money_fields:
                norm = self._format_currency_str(value_str)
                if norm is not None:
                    value_str = norm
            
            display_key = config.ENTITY_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            
            if self._is_value_valid(value_str): # Confidence already enforced above
                grid_column_start = current_col_pair * 3
                
                self._add_entity_editable_field(self.entities_grid_container, row_idx, grid_column_start, display_key, value_str)
                
                if current_col_pair == 0:
                    current_col_pair = 1
                else:
                    current_col_pair = 0
                    row_idx += 1

        if current_col_pair == 1: # Adjust row if last pair was only one column
            row_idx += 1 

        return row_idx 

    def _display_error_messages(self, current_row: int, all_results: List[AnalysisResult]) -> int:
        error_messages_found = False
        for result in all_results:
            if result.error:
                error_messages_found = True
                error_label = ttk.Label(self.entities_grid_container, text=f"Analysis Error ({result.document_id}): {result.error}", foreground="red", wraplength=500, justify="left")
                error_label.grid(row=current_row, column=0, sticky="w", padx=5, pady=2, columnspan=6)
                self.error_labels.append(error_label)
                logger.warning(f"ResultsWindow: Added error row for {result.document_id}: {result.error[:50]}...")
                current_row += 1
        
        if error_messages_found:
            current_row += 1
        return current_row

    def _display_legal_description_section(self, current_row: int) -> int:
        legal_present_cv: ConfidenceValue = self.combined_entities.LegalDescriptionPresent
        legal_detail_cv: ConfidenceValue = self.combined_entities.LegalDescriptionDetail
        
        legal_present_value = self._get_underlying_value(legal_present_cv)
        legal_detail_value = self._get_underlying_value(legal_detail_cv)

        # Only display this section if at least one field meets the UI confidence threshold
        if (float(legal_present_cv.confidence or 0.0) >= config.UI_CONFIDENCE_MIN) or (float(legal_detail_cv.confidence or 0.0) >= config.UI_CONFIDENCE_MIN):
            # LegalDescriptionPresent
            if float(legal_present_cv.confidence or 0.0) >= config.UI_CONFIDENCE_MIN:
                ttk.Label(self.entities_grid_container, text=f"{config.ENTITY_DISPLAY_NAMES.get('LegalDescriptionPresent', 'Legal Description Present')}:", font=("Arial", 9, "bold")).grid(row=current_row, column=0, sticky="nw", pady=(10, 0), padx=5, columnspan=2)
                current_row += 1
                ttk.Label(self.entities_grid_container, text=legal_present_value, font=("Arial", 9), wraplength=self.winfo_width() - 40, justify="left").grid(row=current_row, column=0, sticky="nw", pady=(2, 10), padx=5, columnspan=6)
                current_row += 1

            # LegalDescriptionDetail
            if float(legal_detail_cv.confidence or 0.0) >= config.UI_CONFIDENCE_MIN:
                ttk.Label(self.entities_grid_container, text=f"{config.ENTITY_DISPLAY_NAMES.get('LegalDescriptionDetail', 'Legal Description Detail')}:", font=("Arial", 9, "bold")).grid(row=current_row, column=0, sticky="nw", pady=(10, 0), padx=5, columnspan=2)
                current_row += 1
                
                if not self.legal_description_detail_text_widget or not self.legal_description_detail_text_widget.winfo_exists():
                    self.legal_description_detail_text_widget = tk.Text(self.entities_grid_container, height=8, wrap=tk.WORD, font=("Arial", 9))
                self.legal_description_detail_text_widget.grid(row=current_row, column=0, sticky="nsew", padx=5, pady=5, columnspan=6)
                current_row += 1
                
                self.legal_description_detail_text_widget.config(state=tk.NORMAL)
                self.legal_description_detail_text_widget.delete(1.0, tk.END)
                self.legal_description_detail_text_widget.insert(tk.END, legal_detail_value)

                if not hasattr(self, 'copy_legal_description_btn') or not self.copy_legal_description_btn.winfo_exists():
                    self.copy_legal_description_btn = ttk.Button(self.entities_grid_container, text="📋", command=self._copy_legal_description_to_clipboard)
                self.copy_legal_description_btn.grid(row=current_row, column=0, pady=5, padx=5, sticky="w", columnspan=6)
                current_row += 1

        return current_row

    def _populate_content(self, all_analysis_results: List[AnalysisResult]):
        self.all_analysis_results = all_analysis_results
        self._clear_grid_widgets()

        logger.info(f"ResultsWindow: Populating content with {len(all_analysis_results)} analysis results.")

        self.combined_entities = self._combine_analysis_results(all_analysis_results)

        current_row = self._display_entity_fields(self.combined_entities)
        current_row = self._display_error_messages(current_row, all_analysis_results)
        current_row = self._display_legal_description_section(current_row)

        self.update_idletasks()

    def update_data(self, new_all_analysis_results: List[AnalysisResult]):
        logger.info("ResultsWindow: Updating data with new analysis result list.")
        self._populate_content(new_all_analysis_results)
        self.lift()
        self.focus_force()
        self.update()

    def _add_entity_editable_field(self, parent_frame: ttk.Frame, row: int, col_start: int, key: str, value: str):
        label = ttk.Label(parent_frame, text=f"{key}:", font=("Arial", 9, "bold"))
        label.grid(row=row, column=col_start, sticky="w", padx=(10, 2), pady=3)

        entry = ttk.Entry(parent_frame, width=30)
        entry.insert(0, value)
        entry.grid(row=row, column=col_start + 1, sticky="ew", padx=(0, 2), pady=3)
        self.entity_entries[key] = entry

        # Use a simple, widely-supported label for the copy button
        copy_btn = ttk.Button(parent_frame, text="📋", width=4)
        # Bind command after creation so we can reference the button itself
        copy_btn.config(command=lambda entry_widget=entry, btn=copy_btn: self._copy_to_clipboard(entry_widget.get(), btn=btn))
        copy_btn.grid(row=row, column=col_start + 2, sticky="w", padx=(0, 10), pady=3)

    def _save_edits_to_global_entities(self):
        logger.info("Saving edited entity values back to global results.")
        latest_result = self.all_analysis_results[-1] if self.all_analysis_results else None
        if not latest_result or not latest_result.entities:
            messagebox.showwarning("No Data", "No analysis result to save edits to.")
            return
            
        reverse_entity_display_names = {v: k for k, v in config.ENTITY_DISPLAY_NAMES.items()}

        for display_key, entry_widget in self.entity_entries.items():
            new_value_str = entry_widget.get().strip()
            
            original_key = reverse_entity_display_names.get(display_key, None)
            if original_key is None:
                original_key = "".join(word.capitalize() for word in display_key.split(" "))
            
            # Retrieve the existing ConfidenceValue object for this field
            current_cv: ConfidenceValue = getattr(latest_result.entities, original_key, ConfidenceValue())
            
            money_fields = tuple(getattr(config, 'MONEY_FIELDS', ["LoanAmount", "RecordingCost"]))
            if original_key in money_fields:
                norm = self._format_currency_str(new_value_str)
                current_cv.value = norm if norm is not None else new_value_str
            elif original_key == "Borrower":
                logger.warning(f"Editing complex field '{original_key}' as plain text. Saving raw string to ConfidenceValue.value.")
                current_cv.value = new_value_str
            elif original_key == "RidersPresent":
                logger.warning(f"Editing of complex field '{original_key}' as a plain string in UI. Value saved as-is in ConfidenceValue.value: {new_value_str}")
                current_cv.value = new_value_str 
            elif hasattr(latest_result.entities, original_key):
                current_cv.value = new_value_str
            else:
                logger.debug(f"Unknown entity key '{original_key}' - cannot update model attribute.")
            
            # Set the updated ConfidenceValue back to the entity
            setattr(latest_result.entities, original_key, current_cv)
        
        if self.legal_description_detail_text_widget and self.legal_description_detail_text_widget.winfo_exists():
            legal_desc_detail_text = self.legal_description_detail_text_widget.get(1.0, tk.END).strip()
            
            legal_detail_cv: ConfidenceValue = latest_result.entities.LegalDescriptionDetail
            legal_detail_cv.value = legal_desc_detail_text
            setattr(latest_result.entities, 'LegalDescriptionDetail', legal_detail_cv)

            legal_present_cv: ConfidenceValue = latest_result.entities.LegalDescriptionPresent
            if legal_desc_detail_text and legal_desc_detail_text != "N/A" and legal_desc_detail_text != "legal description is missing":
                legal_present_cv.value = "Yes"
            else:
                legal_present_cv.value = "No"
            setattr(latest_result.entities, 'LegalDescriptionPresent', legal_present_cv)

        # Provide subtle, inline confirmation instead of a popup
        try:
            if hasattr(self, 'save_button') and self.save_button.winfo_exists():
                self._flash_button(self.save_button, flash_text="Saved ✓")
        except Exception:
            pass

    # Export functionality removed per request.

    def _copy_to_clipboard(self, text: str, btn: Optional[ttk.Button] = None):
        try:
            self.clipboard_clear()
            self.clipboard_append(str(text))
            self.update_idletasks()
            # Subtle feedback instead of popup
            try:
                if btn and btn.winfo_exists():
                    self._flash_button(btn, flash_text="Copied ✓")
            except Exception:
                pass
            logger.info(f"Copied '{text[:50]}...' to clipboard.")
        except Exception as e:
            messagebox.showerror("Copy Error", f"Failed to copy text: {e}")
            logger.error(f"Error copying text to clipboard: {e}", exc_info=True)

    def _copy_legal_description_to_clipboard(self):
        latest_result = self.all_analysis_results[-1] if self.all_analysis_results else None
        if latest_result and latest_result.entities and latest_result.entities.LegalDescriptionDetail.value:
            text_to_copy = latest_result.entities.LegalDescriptionDetail.value
        else:
            text_to_copy = "No legal description available to copy."

        # Pass the button for subtle visual feedback
        try:
            btn = getattr(self, 'copy_legal_description_btn', None)
        except Exception:
            btn = None
        self._copy_to_clipboard(text_to_copy, btn=btn)

    def _on_capture_new_document_clicked(self):
        logger.info("ResultsWindow: 'Capture New Document' clicked.")
        if self.on_new_capture_callback:
            self.on_new_capture_callback()
        else:
            logger.warning("on_new_capture_callback is not set.")

    def _on_start_new_session_clicked(self):
        logger.info("ResultsWindow: 'Start New Session' clicked.")
        if self.on_start_new_session_callback:
            self.on_start_new_session_callback()
        else:
            logger.warning("on_start_new_session_callback is not set.")

    def _on_closing(self):
        logger.info("ResultsWindow: Window closed by user (X button). Destroying window.")
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()
