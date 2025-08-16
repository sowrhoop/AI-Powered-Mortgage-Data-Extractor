import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Callable, Any, List, Dict, Optional
from models.document_entities import AnalysisResult, MortgageDocumentEntities, Rider
from dataclasses import asdict
import re
import difflib # Import difflib for sequence matching
from config import ENTITY_DISPLAY_NAMES, OUTPUT_FILE_NAME

logger = logging.getLogger(__name__)

class ResultsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, all_analysis_results: List[AnalysisResult],
                 on_new_input_callback: Callable[[], None], on_close_callback: Callable[[], None]): # Added on_close_callback
        super().__init__(parent)
        logger.info("ResultsWindow: Initializing...")
        self.title("Mortgage Document Analysis Results")
        self.geometry("850x750")
        self.minsize(600, 500)

        self.all_analysis_results = all_analysis_results
        self.on_new_capture_callback: Optional[Callable[[], None]] = on_new_input_callback
        self.on_start_new_session_callback: Optional[Callable[[], None]] = None
        self.on_close_callback = on_close_callback # Store the close callback

        self.entity_entries: Dict[str, tk.Entry] = {}
        self.combined_entities: Dict[str, Any] = {}
        self.legal_description_detail_text_widget: Optional[tk.Text] = None # Initialize as Optional

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.attributes("-topmost", True)
        self.update_idletasks()
        self._position_window_on_right_half()

        self._create_widgets_layout()
        # Always populate content, even if it's just the default dummy result
        self._populate_content(self.all_analysis_results) 
        logger.info("ResultsWindow: Widgets created and content populated.")

        self.lift()
        self.focus_force()
        self.update()
        logger.info("Results window created and displayed (attempted to bring to front and focus).")

    def _position_window_on_right_half(self):
        """Positions the results window to occupy the right half of the main screen."""
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        width = screen_width // 2
        height = screen_height
        x = screen_width // 2
        y = 0

        self.geometry(f"{width}x{height}+{x}+{y}")
        logger.debug(f"ResultsWindow: Snapped to right half [{width}x{height}] at ({x},{y})")

    def _create_widgets_layout(self):
        """Creates the static layout of the results window (notebook, frames, buttons)."""
        main_content_frame = ttk.Frame(self, padding="10")
        main_content_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        self.entities_grid_container = ttk.Frame(main_content_frame)
        self.entities_grid_container.pack(expand=True, fill=tk.BOTH)

        # Configure columns for a two-column display with proper spacing and expansion
        # Column 0: Label for the first item (fixed width, or minimal weight)
        # Column 1: Entry for the first item (expands)
        # Column 2: Copy button for the first item (fixed width)
        # Column 3: Label for the second item (fixed width, or minimal weight)
        # Column 4: Entry for the second item (expands)
        # Column 5: Copy button for the second item (fixed width)
        self.entities_grid_container.grid_columnconfigure(0, weight=0) # Label 1
        self.entities_grid_container.grid_columnconfigure(1, weight=1) # Entry 1
        self.entities_grid_container.grid_columnconfigure(2, weight=0) # Copy Btn 1
        self.entities_grid_container.grid_columnconfigure(3, weight=0) # Label 2
        self.entities_grid_container.grid_columnconfigure(4, weight=1) # Entry 2
        self.entities_grid_container.grid_columnconfigure(5, weight=0) # Copy Btn 2


        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(pady=10)

        self.capture_new_doc_btn = ttk.Button(self.button_frame, text="Capture New Document", command=self._on_capture_new_document_clicked)
        self.capture_new_doc_btn.pack(side=tk.LEFT, padx=5)
        
        save_button = ttk.Button(self.button_frame, text="Save Edits", command=self._save_edits_to_global_entities)
        save_button.pack(side=tk.LEFT, padx=5)

        self.start_new_session_btn = ttk.Button(self.button_frame, text="Start New Session", command=self._on_start_new_session_clicked)
        self.start_new_session_btn.pack(side=tk.LEFT, padx=5)

    def set_capture_callbacks(self, on_new_capture_callback: Callable[[], None], on_start_new_session_callback: Callable[[], None]):
        """
        Sets the specific callbacks for the capture buttons.
        This is called by main.py after the ResultsWindow is initialized.
        """
        self.on_new_capture_callback = on_new_capture_callback
        self.on_start_new_session_callback = on_start_new_session_callback
        self.capture_new_doc_btn.config(command=self._on_capture_new_document_clicked)
        self.start_new_session_btn.config(command=self._on_start_new_session_clicked)
        logger.info("ResultsWindow: Capture callbacks set.")

    def add_settings_button(self, command: Callable):
        """Adds a settings button to the results window's button frame."""
        settings_button = ttk.Button(self.button_frame, text="Settings", command=command)
        settings_button.pack(side=tk.RIGHT, padx=5)

    def _normalize_string_for_comparison(self, s: str) -> str:
        """Removes non-alphanumeric characters and converts to lowercase for comparison."""
        return re.sub(r'[^a-z0-9]', '', s.lower())

    def is_similar_name(self, existing_names: set, new_name: str, threshold: float = 0.85) -> bool:
        """
        Checks if a new name is similar to any existing names in a set using difflib.SequenceMatcher.
        This allows for better detection of near-duplicates even with minor spelling differences.
        """
        norm_new_name = self._normalize_string_for_comparison(new_name)
        if not norm_new_name:
            return False

        for existing_name in existing_names:
            norm_existing_name = self._normalize_string_for_comparison(existing_name)
            if not norm_existing_name:
                continue

            # Calculate similarity ratio using SequenceMatcher
            s = difflib.SequenceMatcher(None, norm_new_name, norm_existing_name)
            if s.ratio() >= threshold:
                logger.debug(f"Found similar name: '{new_name}' (normalized '{norm_new_name}') is similar to '{existing_name}' (normalized '{norm_existing_name}') with ratio {s.ratio():.2f}")
                return True
        return False

    def _clear_grid_widgets(self):
        """Clears all widgets from the entities grid container."""
        for widget in self.entities_grid_container.winfo_children():
            widget.destroy()
        self.entity_entries.clear()

    def _is_value_valid(self, value: Any) -> bool:
        """Checks if a value is considered 'valid' (not N/A, empty, etc.)."""
        if value is None:
            return False
        if isinstance(value, str):
            normalized_value = value.strip().lower()
            # Only consider "No" as invalid for boolean-like fields if not specifically intended to be displayed as "No"
            # For general text fields, "" or "n/a" implies not extracted.
            return normalized_value not in ["n/a", "not listed", "legal description is missing", ""] and value.strip() != "No" # Added check for "No"
        if isinstance(value, list):
            return bool(value) # True if list is not empty
        if isinstance(value, dict):
            return bool(value) # True if dict is not empty
        return True # For other types like int, float, consider them valid if not None

    def _combine_analysis_results(self, all_results: List[AnalysisResult]) -> Dict[str, Any]:
        """
        Combines entities from all analysis results, prioritizing valid information
        and performing deduplication for list-based entities.
        """
        combined: Dict[str, Any] = {}
        
        # If there are no results or only the initial dummy result,
        # initialize combined with default MortgageDocumentEntities values.
        if not all_results or (len(all_results) == 1 and all_results[0].document_id == "Document_0"):
            return asdict(MortgageDocumentEntities())

        for result in all_results: # Iterate through all results from oldest to newest
            if result.error or not result.entities:
                if result.error:
                    error_key = f"Error ({result.document_id})"
                    if error_key not in combined:
                        combined[error_key] = result.error
                continue

            current_entities_dict = asdict(result.entities)

            for key, current_value in current_entities_dict.items():
                if key == "BorrowerNames":
                    existing_names = set(combined.get(key, []))
                    if isinstance(current_value, list):
                        for name in current_value:
                            cleaned_name = name.strip()
                            if self._is_value_valid(cleaned_name) and not self.is_similar_name(existing_names, cleaned_name):
                                existing_names.add(cleaned_name)
                    combined[key] = sorted(list(existing_names))
                
                # --- NEW/UPDATED LOGIC FOR OTHER LIST FIELDS ---
                elif key in ["BorrowerAlias", "BorrowerWithRelationship", "BorrowerWithTenantInformation"]:
                    existing_items = set(combined.get(key, [])) # Use a set to handle duplicates
                    if isinstance(current_value, list):
                        for item in current_value:
                            cleaned_item = str(item).strip() # Ensure it's a string and strip whitespace
                            if self._is_value_valid(cleaned_item):
                                existing_items.add(cleaned_item)
                    # If multiple items, store as sorted list. If no valid items, ensure it's an empty list.
                    if existing_items:
                        combined[key] = sorted(list(existing_items))
                    elif key not in combined: # Only if key was never added before
                        combined[key] = [] # Ensure it's an empty list by default if nothing found
                # --- END NEW/UPDATED LOGIC ---
                
                elif key == "RidersPresent":
                    existing_riders_map = {r.Name: r for r in combined.get(key, []) if isinstance(r, Rider)}
                    if isinstance(current_value, list):
                        for rider_data in current_value:
                            if isinstance(rider_data, dict):
                                rider_obj = Rider(Name=rider_data.get("Name", "N/A"), SignedAttached=rider_data.get("SignedAttached", "No"))
                            elif isinstance(rider_data, Rider):
                                rider_obj = rider_data
                            else:
                                continue

                            if self._is_value_valid(rider_obj.Name):
                                # If a rider with this name already exists, update its signed status if current is 'Yes'
                                # Or just overwrite if we want latest. For simplicity, let's just overwrite.
                                existing_riders_map[rider_obj.Name] = rider_obj
                    combined[key] = list(existing_riders_map.values())

                elif key == "LegalDescriptionDetail":
                    existing_detail = combined.get(key, "N/A")
                    if self._is_value_valid(current_value):
                        if not self._is_value_valid(existing_detail) or (current_value.strip() != existing_detail.strip()):
                            combined[key] = current_value
                            combined["LegalDescriptionPresent"] = "Yes"
                    elif key not in combined:
                        combined[key] = current_value
                        
                elif key == "LegalDescriptionPresent":
                    if self._is_value_valid(current_value) and current_value == "Yes":
                        combined[key] = "Yes"
                    elif key not in combined and not self._is_value_valid(current_value):
                        combined[key] = current_value
                
                elif key == "LoanAmount":
                    cleaned_amount = re.sub(r'[$,]', '', str(current_value).strip())
                    if self._is_value_valid(cleaned_amount):
                        combined[key] = cleaned_amount
                    elif key not in combined:
                        combined[key] = current_value
                else: # For all other single-value fields (strings, int, etc.)
                    # Prioritize a valid new value over an existing invalid one, or if not yet set
                    if not self._is_value_valid(combined.get(key)) and self._is_value_valid(current_value):
                        combined[key] = current_value
                    elif key not in combined: # If key still not in combined and current_value is also invalid
                        combined[key] = current_value # Initialize with its value (e.g., 'N/A')

        # Final check for LegalDescriptionPresent if detail was never validly extracted
        if "LegalDescriptionDetail" in combined and not self._is_value_valid(combined["LegalDescriptionDetail"]):
            combined["LegalDescriptionPresent"] = "No"
        elif "LegalDescriptionPresent" not in combined:
             combined["LegalDescriptionPresent"] = "No" # Default if nothing found


        return combined

    def _display_entity_fields(self, entities_to_display: Dict[str, Any]):
        """
        Dynamically displays the extracted entities in a two-column grid with editable fields.
        Only displays entities that have valid, extracted values.
        """
        row_idx = 0
        current_col_pair = 0 # 0 for left pair (cols 0,1,2), 1 for right pair (cols 3,4,5)

        # Always include DocumentType for context if it's extracted
        doc_type_value = entities_to_display.get("DocumentType", "N/A")
        if self._is_value_valid(doc_type_value):
            display_key = ENTITY_DISPLAY_NAMES.get("DocumentType", "Document Type")
            self._add_entity_editable_field(self.entities_grid_container, row_idx, 0, display_key, doc_type_value)
            current_col_pair = 1 # Next item goes to the right column
        
        # Filter other entities to only include valid ones for display
        # Exclude DocumentType, LegalDescriptionPresent, LegalDescriptionDetail as they are handled specifically
        # Also exclude PageCount and MissingPages since they are removed
        other_entities = sorted([
            (k, v) for k, v in entities_to_display.items()
            if k not in ["DocumentType", "LegalDescriptionPresent", "LegalDescriptionDetail", "Error (Document_0)", "PageCount", "MissingPages"]
            and self._is_value_valid(v) # Only include if the value is valid
        ], key=lambda item: item[0]) # Sorting by key for consistent order

        for i, (key, value) in enumerate(other_entities):
            value_str = ""
            if isinstance(value, list):
                if key == "RidersPresent":
                    value_str = "\n".join([
                        f"{r.Name} (Signed: {r.SignedAttached})"
                        for r in value if isinstance(r, Rider)
                    ])
                elif key == "BorrowerNames":
                    value_str = ", ".join(map(str, value))
                # This 'else' will now correctly catch BorrowerAlias, BorrowerWithRelationship, BorrowerWithTenantInformation
                else: 
                    value_str = ", ".join(map(str, value))
            elif isinstance(value, dict):
                value_str = ", ".join([f"{k}: {v}" for k, v in value.items()])
            else:
                value_str = str(value)

            # Apply dollar symbol removal for LoanAmount specifically at display
            if key == "LoanAmount":
                value_str = re.sub(r'[$,]', '', value_str).strip()
            
            display_key = ENTITY_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            
            grid_column_start = current_col_pair * 3 # 0 or 3
            
            self._add_entity_editable_field(self.entities_grid_container, row_idx, grid_column_start, display_key, value_str)
            
            if current_col_pair == 0:
                current_col_pair = 1
            else:
                current_col_pair = 0
                row_idx += 1 # Move to next row after filling both columns in a pair

        if current_col_pair == 1: # If the last item was in the first column, ensure the next row starts correctly
            row_idx += 1 

        return row_idx 


    def _display_error_messages(self, current_row: int, all_results: List[AnalysisResult]) -> int:
        """Displays error messages from analysis results."""
        error_messages_found = False
        for result in all_results:
            if result.error:
                error_messages_found = True
                error_label = ttk.Label(self.entities_grid_container, text=f"Analysis Error ({result.document_id}): {result.error}", foreground="red", wraplength=500, justify="left")
                error_label.grid(row=current_row, column=0, sticky="w", padx=5, pady=2, columnspan=6)
                logger.warning(f"ResultsWindow: Added error row for {result.document_id}: {result.error[:50]}...")
                current_row += 1
        
        if error_messages_found:
            current_row += 1
        return current_row

    def _display_legal_description_section(self, current_row: int) -> int:
        """Displays the legal description section only if present."""
        legal_present = self.combined_entities.get("LegalDescriptionPresent", "No")
        legal_detail = self.combined_entities.get("LegalDescriptionDetail", "N/A")

        # Only display the legal description section if LegalDescriptionPresent is "Yes"
        # or if there is actual legal detail present.
        if legal_present == "Yes" or self._is_value_valid(legal_detail):
            ttk.Label(self.entities_grid_container, text=f"{ENTITY_DISPLAY_NAMES.get('LegalDescriptionPresent', 'Legal Description Present')}:", font=("Arial", 9, "bold")).grid(row=current_row, column=0, sticky="nw", pady=(10, 0), padx=5, columnspan=2)
            current_row += 1
            ttk.Label(self.entities_grid_container, text=legal_present, font=("Arial", 9), wraplength=self.winfo_width() - 40, justify="left").grid(row=current_row, column=0, sticky="nw", pady=(2, 10), padx=5, columnspan=6)
            current_row += 1
            
            ttk.Label(self.entities_grid_container, text=f"{ENTITY_DISPLAY_NAMES.get('LegalDescriptionDetail', 'Legal Description Detail')}:", font=("Arial", 9, "bold")).grid(row=current_row, column=0, sticky="nw", pady=(10, 0), padx=5, columnspan=2)
            current_row += 1
            
            if not self.legal_description_detail_text_widget or not self.legal_description_detail_text_widget.winfo_exists():
                self.legal_description_detail_text_widget = tk.Text(self.entities_grid_container, height=8, wrap=tk.WORD, font=("Arial", 9))
            self.legal_description_detail_text_widget.grid(row=current_row, column=0, sticky="nsew", padx=5, pady=5, columnspan=6)
            current_row += 1
            
            self.legal_description_detail_text_widget.config(state=tk.NORMAL)
            self.legal_description_detail_text_widget.delete(1.0, tk.END)
            self.legal_description_detail_text_widget.insert(tk.END, legal_detail)

            if not hasattr(self, 'copy_legal_description_btn') or not self.copy_legal_description_btn.winfo_exists():
                self.copy_legal_description_btn = ttk.Button(self.entities_grid_container, text="Copy Legal", command=self._copy_legal_description_to_clipboard)
            self.copy_legal_description_btn.grid(row=current_row, column=0, pady=5, padx=5, sticky="w", columnspan=6)
            current_row += 1
        
        return current_row

    def _populate_content(self, all_analysis_results: List[AnalysisResult]):
        """
        Populates the results window with combined analysis data from all documents.
        Always displays all entity fields (even if N/A initially), along with any errors.
        """
        self.all_analysis_results = all_analysis_results
        self._clear_grid_widgets()

        logger.info(f"ResultsWindow: Populating content with {len(all_analysis_results)} analysis results.")

        # Combine entities from all results, which will include default N/A values if no real data
        self.combined_entities = self._combine_analysis_results(all_analysis_results)

        # Always display entity fields
        current_row = self._display_entity_fields(self.combined_entities)

        # Display error messages if any are present
        current_row = self._display_error_messages(current_row, all_analysis_results)

        # Always display legal description section
        current_row = self._display_legal_description_section(current_row)

        self.update_idletasks() # Ensure layout is updated after adding widgets


    def update_data(self, new_all_analysis_results: List[AnalysisResult]):
        """
        Updates the content of the ResultsWindow with new analysis data.
        :param new_all_analysis_results: The updated list of AnalysisResult objects to display.
        """
        logger.info("ResultsWindow: Updating data with new analysis result list.")
        self._populate_content(new_all_analysis_results)
        self.lift()
        self.focus_force()
        self.update()

    def _add_entity_editable_field(self, parent_frame: ttk.Frame, row: int, col_start: int, key: str, value: str):
        """
        Adds a label, an editable entry field, and a copy button for an entity to the given parent frame.
        Uses grid layout for alignment.
        """
        label = ttk.Label(parent_frame, text=f"{key}:", font=("Arial", 9, "bold"))
        # Adjust padx for better alignment. Use sticky="w" for left alignment.
        label.grid(row=row, column=col_start, sticky="w", padx=(10, 2), pady=3)

        entry = ttk.Entry(parent_frame, width=30)
        entry.insert(0, value)
        # Adjust padx for better alignment. Use sticky="ew" for expansion.
        entry.grid(row=row, column=col_start + 1, sticky="ew", padx=(0, 2), pady=3)
        self.entity_entries[key] = entry

        copy_btn = ttk.Button(parent_frame, text="📋", width=2, command=lambda val=value: self._copy_to_clipboard(val))
        # Adjust padx for better alignment. Use sticky="w" for left alignment.
        copy_btn.grid(row=row, column=col_start + 2, sticky="w", padx=(0, 10), pady=3)


    def _save_edits_to_global_entities(self):
        """
        Saves the edited values from the UI entry fields back into the latest
        AnalysisResult's entities.
        """
        logger.info("Saving edited entity values back to global results.")
        latest_result = self.all_analysis_results[-1] if self.all_analysis_results else None
        if not latest_result or not latest_result.entities:
            messagebox.showwarning("No Data", "No analysis result to save edits to.")
            return
            
        for display_key, entry_widget in self.entity_entries.items():
            new_value = entry_widget.get().strip()
            original_key = next((k for k, v in ENTITY_DISPLAY_NAMES.items() if v == display_key), display_key) # Corrected line

            # Special handling for LoanAmount to remove any symbols before saving
            if original_key == "LoanAmount":
                new_value = re.sub(r'[$,]', '', new_value).strip()

            if original_key == "BorrowerNames":
                latest_result.entities.BorrowerNames = [name.strip() for name in new_value.split(',') if name.strip()]
            elif original_key in ["BorrowerAlias", "BorrowerWithRelationship", "BorrowerWithTenantInformation"]: # New: Handle other list fields
                latest_result.entities.__setattr__(original_key, [item.strip() for item in new_value.split(',') if item.strip()])
            elif original_key == "RidersPresent":
                # For RidersPresent, if the user edits the text field, we'll save it as a string for now.
                # A more robust solution would involve parsing the string back into Rider objects.
                logger.warning(f"Editing of complex field '{original_key}' as a plain string. Value saved as-is: {new_value}")
                if hasattr(latest_result.entities, original_key):
                    setattr(latest_result.entities, original_key, new_value)
            elif hasattr(latest_result.entities, original_key):
                # PageCount and MissingPages are removed, so no special handling for int here.
                setattr(latest_result.entities, original_key, new_value)
            else:
                logger.debug(f"Unknown entity key '{original_key}' — cannot update model attribute.")
        
        if self.legal_description_detail_text_widget and self.legal_description_detail_text_widget.winfo_exists():
            legal_desc_detail_text = self.legal_description_detail_text_widget.get(1.0, tk.END).strip()
            latest_result.entities.LegalDescriptionDetail = legal_desc_detail_text
            if legal_desc_detail_text and legal_desc_detail_text != "N/A" and legal_desc_detail_text != "legal description is missing":
                latest_result.entities.LegalDescriptionPresent = "Yes"
            else:
                latest_result.entities.LegalDescriptionPresent = "No"


        messagebox.showinfo("Edits Saved", "Your changes have been saved to the current analysis result.")

    def _copy_to_clipboard(self, text: str):
        """Copies the given text to the system clipboard."""
        try:
            self.clipboard_clear()
            self.clipboard_append(str(text))
            self.update_idletasks()
            messagebox.showinfo("Copied", "Text copied to clipboard!")
            logger.info(f"Copied '{text[:50]}...' to clipboard.")
        except Exception as e:
            messagebox.showerror("Copy Error", f"Failed to copy text: {e}")
            logger.error(f"Error copying text to clipboard: {e}", exc_info=True)

    def _copy_legal_description_to_clipboard(self):
        """Copies the legal description detail from the latest document to the clipboard."""
        latest_result = self.all_analysis_results[-1] if self.all_analysis_results else None
        if latest_result and latest_result.entities and latest_result.entities.LegalDescriptionDetail:
            text_to_copy = latest_result.entities.LegalDescriptionDetail
        else:
            text_to_copy = "No legal description available to copy."

        self._copy_to_clipboard(text_to_copy)


    def _on_capture_new_document_clicked(self):
        """
        Handles the 'Capture New Document' button click, triggering a new capture
        that adds to the current session.
        """
        logger.info("ResultsWindow: 'Capture New Document' clicked.")
        if self.on_new_capture_callback:
            self.on_new_capture_callback()
        else:
            logger.warning("on_new_capture_callback is not set.")

    def _on_start_new_session_clicked(self):
        """
        Handles the 'Start New Session' button click, clearing all data.
        """
        logger.info("ResultsWindow: 'Start New Session' clicked.")
        if self.on_start_new_session_callback:
            self.on_start_new_session_callback()
        else:
            logger.warning("on_start_new_session_callback is not set.")

    def _on_closing(self):
        """Handles the window close (X) button event. This will destroy the window."""
        logger.info("ResultsWindow: Window closed by user (X button). Destroying window.")
        if self.on_close_callback:
            self.on_close_callback() # Call the callback to notify the main app
        self.destroy()