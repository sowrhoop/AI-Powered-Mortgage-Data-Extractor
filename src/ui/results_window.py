import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
from typing import Callable, Any, List, Dict
from models.document_entities import AnalysisResult, MortgageDocumentEntities, Rider # Import your structured models
from dataclasses import asdict # Import asdict for converting dataclass to dict
import math # For ceil function

logger = logging.getLogger(__name__)

class ResultsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, all_analysis_results: List[AnalysisResult], on_new_input_callback: Callable[[], None]):
        super().__init__(parent)
        logger.info("ResultsWindow: Initializing...")
        self.title("Mortgage Document Analysis Results")
        # Initial geometry set to ensure it's visible before centering
        self.geometry("850x750")
        self.minsize(600, 500) # Minimum size for resizing

        self.all_analysis_results = all_analysis_results # Store the list of all results
        self.on_new_input_callback = on_new_input_callback
        self.entity_entries: Dict[str, tk.Entry] = {}

        self.protocol("WM_DELETE_WINDOW", self._on_closing) # Handle window close button

        # --- IMPORTANT: Ensure the window is always on top, centered, and gets focus ---
        self.attributes("-topmost", True) # Keep this window on top of others
        self.update_idletasks() # Ensure window dimensions are calculated before centering
        self._center_window() # Center the window on the screen (actually positions it on the right)

        self._create_widgets_layout() # Create static layout (notebook, frames, buttons)
        self._populate_content(self.all_analysis_results) # Populate with initial data
        logger.info("ResultsWindow: Widgets created and content populated.")

        # Explicitly bring to front and give focus after widgets are created
        self.lift() # Bring window to the top of the stacking order
        self.focus_force() # Force keyboard focus to this window
        self.update() # Force a redraw to ensure it's visible
        self.entity_entries: Dict[str, tk.Entry] = {}


        logger.info("Results window created and displayed (attempted to bring to front and focus).")

    def _center_window(self):
        """
        Positions the results window to occupy the right half of the main screen.
        """
        self.update_idletasks() # Ensure window is fully rendered for accurate dimension calculations
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        width = screen_width // 2
        height = screen_height
        x = screen_width // 2 # Start X coordinate at the middle of the screen
        y = 0 # Start Y coordinate at the top

        self.geometry(f"{width}x{height}+{x}+{y}")
        logger.debug(f"ResultsWindow: Snapped to right half [{width}x{height}] at ({x},{y})")

    def _create_widgets_layout(self):
        """
        Creates the static layout of the results window (notebook, frames, buttons).
        This method is called only once during initialization.
        """
        # --- Main Frame for all content ---
        main_content_frame = ttk.Frame(self)
        main_content_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # --- Extracted Entities Grid Container ---
        self.entities_grid_container = ttk.Frame(main_content_frame)
        self.entities_grid_container.pack(expand=True, fill=tk.BOTH)

        # Configure columns to expand
        self.entities_grid_container.grid_columnconfigure(0, weight=0) # Label column
        self.entities_grid_container.grid_columnconfigure(1, weight=1) # Entry column
        self.entities_grid_container.grid_columnconfigure(2, weight=0) # Label column (for 2nd column of data)
        self.entities_grid_container.grid_columnconfigure(3, weight=1) # Entry column (for 2nd column of data)


        # --- Control Buttons ---
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        new_input_btn = ttk.Button(button_frame, text="Capture New Document", command=self._on_new_input_clicked)
        new_input_btn.pack(side=tk.LEFT, padx=5)
        save_button = ttk.Button(button_frame, text="Save Edits", command=self._save_edits_to_global_entities)
        save_button.pack(side=tk.LEFT, padx=5)


        # --- Processing Message Overlay ---
        # This frame will overlay the content when processing
        self.processing_message_frame = ttk.Frame(self, relief=tk.RAISED, borderwidth=2, style="Processing.TFrame")
        self.processing_message_label = ttk.Label(
            self.processing_message_frame,
            text="Processing document, please wait...",
            font=("Arial", 14, "bold"),
            anchor="center"
        )
        self.processing_message_label.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        # Initially hide it
        self.processing_message_frame.place_forget()

        # Style for the processing message frame (optional, for better visual)
        self.style = ttk.Style()
        self.style.configure("Processing.TFrame", background="#e0e0e0") # Light grey background
        self.style.configure("Processing.TLabel", background="#e0e0e0", foreground="#333333")


    def _populate_content(self, all_analysis_results: List[AnalysisResult]):
        # Clear previous widgets from the grid container
        for widget in self.entities_grid_container.winfo_children():
            widget.destroy()

        logger.info(f"ResultsWindow: Populating content with {len(all_analysis_results)} analysis results.")
        self.all_analysis_results = all_analysis_results # Update the stored list of analysis results
        self.entity_entries.clear() # Clear stored entry references

        combined_entities: Dict[str, Any] = {}

        # Define a consistent order for display
        display_order = [
            "DocumentType", "BorrowerNames", "BorrowerAddress", "LenderName", "TrusteeName", "TrusteeAddress",
            "LoanAmount", "PropertyAddress", "DocumentDate", "MaturityDate", "APN_ParcelID",
            "RecordingStampPresent", "RecordingBook", "RecordingPage", "RecordingDocumentNumber",
            "RecordingDate", "RecordingTime", "ReRecordingInformation", "RecordingCost",
            "PageCount", "MissingPages", "BorrowerSignaturesPresent", "RidersPresent",
            "InitialedChangesPresent", "MERS_RiderSelected", "MERS_RiderSignedAttached",
            "MIN", "LegalDescriptionPresent" # LegalDescriptionDetail will be handled separately
        ]

        # Iterate through results from oldest to newest to prioritize latest valid updates
        for result in all_analysis_results:
            if result.error or not result.entities:
                if result.error:
                    error_key = f"Error ({result.document_id})"
                    combined_entities[error_key] = result.error
                continue

            current_entities_dict = asdict(result.entities)

            for key in display_order:
                current_value = current_entities_dict.get(key)

                if current_value is None:
                    continue

                if key == "BorrowerNames":
                    existing_names = set(combined_entities.get(key, []))
                    if isinstance(current_value, list):
                        for name in current_value:
                            if name and name.strip() != "N/A":
                                existing_names.add(name.strip())
                    combined_entities[key] = sorted(list(existing_names))
                elif key == "RidersPresent":
                    existing_riders = {r['Name']: r for r in combined_entities.get(key, []) if isinstance(r, dict) and 'Name' in r}
                    if isinstance(current_value, list):
                        for rider_dict in current_value:
                            if isinstance(rider_dict, dict) and 'Name' in rider_dict:
                                existing_riders[rider_dict['Name']] = rider_dict
                    combined_entities[key] = list(existing_riders.values())
                elif key == "BorrowerSignaturesPresent":
                    existing_signatures = combined_entities.get(key, {})
                    if isinstance(current_value, dict):
                        existing_signatures.update(current_value)
                    combined_entities[key] = existing_signatures
                elif isinstance(current_value, (str, int, float)):
                    current_str_value = str(current_value).strip()
                    if current_str_value.lower() not in ["n/a", "not listed", ""]:
                        combined_entities[key] = current_str_value
                    elif key not in combined_entities:
                        combined_entities[key] = current_str_value
                elif key not in combined_entities:
                    combined_entities[key] = current_value

        # Determine the number of columns and rows
        # We want to fit all entities and legal description on one page
        # Let's aim for 2 columns.
        num_display_fields = len(display_order) # Number of fields we intend to display in grid
        
        # Add a placeholder for the legal description detail text widget
        # This is not part of the `display_order` because it's a multi-line text widget
        # and will be placed separately below the grid.
        
        # Calculate rows per column for a 2-column layout
        num_columns = 2
        # We need to consider the legal description detail and its copy button as extra rows at the end
        # For now, let's assume the main entities will be split, and legal description comes after.
        
        # Determine the maximum number of entities per column
        # This is a heuristic; actual fitting depends on font size, padding, etc.
        # Let's try to split the main entities evenly across two columns.
        entities_to_display = []
        for key in display_order:
            if key in combined_entities:
                entities_to_display.append((key, combined_entities[key]))

        # Calculate rows per column for the main entities
        rows_per_col = math.ceil(len(entities_to_display) / num_columns)
        
        row_idx = 0
        col_idx = 0

        # Populate main entities in a two-column grid
        for i, (key, value) in enumerate(entities_to_display):
            value_str = ""
            if isinstance(value, list):
                if key == "RidersPresent":
                    value_str = "\n".join([
                        f"{r.get('Name', '')} (Signed: {r.get('SignedAttached', '')})"
                        for r in value if isinstance(r, dict)
                    ])
                else:
                    value_str = ", ".join(map(str, value))
            elif isinstance(value, dict):
                value_str = ", ".join([f"{k}: {v}" for k, v in value.items()])
            else:
                value_str = str(value)

            display_key = key.replace("_", " ").replace("ID", " ID").replace("APN", "APN").replace("MIN", "MIN").title()
            if key == "MIN":
                display_key = "MIN (Mortgage Identification Number)"
            elif key == "BorrowerAddress":
                display_key = "Borrower Address"
            elif key == "TrusteeAddress":
                display_key = "Trustee Address"

            self._add_entity_editable_field(self.entities_grid_container, row_idx, col_idx, display_key, value_str)
            
            row_idx += 1
            if row_idx >= rows_per_col and col_idx == 0:
                row_idx = 0
                col_idx = 1 # Move to the second column

        # Add error messages below the main entity grid, spanning both columns
        current_row_for_errors = max(row_idx, rows_per_col) # Start errors after the longest column
        for result in all_analysis_results:
            if result.error:
                error_label = ttk.Label(self.entities_grid_container, text=f"Analysis Error ({result.document_id}): {result.error}", foreground="red", wraplength=500, justify="left")
                error_label.grid(row=current_row_for_errors, column=0, sticky="w", padx=5, pady=2, columnspan=4) # Span all 4 sub-columns
                logger.warning(f"ResultsWindow: Added error row for {result.document_id}: {result.error[:50]}...")
                current_row_for_errors += 1

        # Populate Legal Description directly below the main entities/errors
        latest_result = self.all_analysis_results[-1] if self.all_analysis_results else None
        if latest_result and latest_result.entities:
            legal_present = latest_result.entities.LegalDescriptionPresent
            legal_detail = latest_result.entities.LegalDescriptionDetail
        else:
            legal_present = "N/A"
            legal_detail = "No legal description available from latest document. Ready for new capture."

        # Add Legal Description Present label
        ttk.Label(self.entities_grid_container, text="Legal Description Present:", font=("Arial", 10, "bold")).grid(row=current_row_for_errors, column=0, sticky="nw", pady=(10, 0), padx=10, columnspan=2)
        current_row_for_errors += 1
        self.legal_description_present_label = ttk.Label(self.entities_grid_container, text=legal_present, font=("Arial", 10), wraplength=self.winfo_width() - 40, justify="left")
        self.legal_description_present_label.grid(row=current_row_for_errors, column=0, sticky="nw", pady=(2, 10), padx=10, columnspan=4)
        current_row_for_errors += 1
        
        # Add Legal Description Detail text widget
        ttk.Label(self.entities_grid_container, text="Legal Description Detail:", font=("Arial", 10, "bold")).grid(row=current_row_for_errors, column=0, sticky="nw", pady=(10, 0), padx=10, columnspan=2)
        current_row_for_errors += 1
        self.legal_description_detail_text_widget = tk.Text(self.entities_grid_container, height=8, wrap=tk.WORD, font=("Arial", 10))

        self.legal_description_detail_text_widget.grid(row=current_row_for_errors, column=0, sticky="nsew", padx=10, pady=5, columnspan=4)
        current_row_for_errors += 1
        
        self.legal_description_detail_text_widget.config(state=tk.NORMAL)
        self.legal_description_detail_text_widget.delete(1.0, tk.END)
        self.legal_description_detail_text_widget.insert(tk.END, legal_detail)
        # self.legal_description_detail_text_widget.config(state=tk.DISABLED)

        # Add Copy button for Legal Description
        self.copy_legal_description_btn = ttk.Button(self.entities_grid_container, text="Copy Legal Description", command=self._copy_legal_description_to_clipboard)
        self.copy_legal_description_btn.grid(row=current_row_for_errors, column=0, pady=5, padx=10, sticky="w", columnspan=4)


    def update_data(self, new_all_analysis_results: List[AnalysisResult]):
        """
        Updates the content of the ResultsWindow with new analysis data.
        :param new_all_analysis_results: The updated list of AnalysisResult objects to display.
        """
        logger.info("ResultsWindow: Updating data with new analysis result list.")
        self._populate_content(new_all_analysis_results)
        self.lift() # Bring to front
        self.focus_force() # Force focus
        self.update() # Force redraw--

    def show_processing_message(self):
        """Shows the processing message overlay."""
        logger.info("ResultsWindow: Showing processing message.")
        # Place the frame in the center, covering a portion of the window
        self.processing_message_frame.place(
            relx=0.5, rely=0.5, anchor=tk.CENTER,
            relwidth=0.6, relheight=0.2
        )
        self.lift() # Bring results window to front
        self.focus_force() # Force focus
        self.update() # Force redraw

    def hide_processing_message(self):
        """Hides the processing message overlay."""
        logger.info("ResultsWindow: Hiding processing message.")
        self.processing_message_frame.place_forget() # Remove the frame from layout
        self.update() # Force redraw

    def _add_entity_editable_field(self, parent_frame: ttk.Frame, row: int, col: int, key: str, value: str):
        """
        Adds a label, an editable entry field, and a copy button for an entity to the given parent frame.
        Uses grid layout for alignment.
        """
        label = ttk.Label(parent_frame, text=f"{key}:", font=("Arial", 9, "bold"))
        label.grid(row=row, column=col * 3, sticky="w", padx=(5, 2), pady=3)

        entry = ttk.Entry(parent_frame, width=30)  # Slightly smaller to make room for copy button
        entry.insert(0, value)
        entry.grid(row=row, column=col * 3 + 1, sticky="ew", padx=(0, 2), pady=3)
        self.entity_entries[key] = entry

        copy_btn = ttk.Button(parent_frame, text="📋", width=2, command=lambda val=value: self._copy_to_clipboard(val))
        copy_btn.grid(row=row, column=col * 3 + 2, sticky="w", padx=(0, 5), pady=3)


    def _save_edits_to_global_entities(self):
        logger.info("Saving edited entity values back to global results.")
        latest_result = self.all_analysis_results[-1] if self.all_analysis_results else None
        if not latest_result or not latest_result.entities:
            return
        for key, entry in self.entity_entries.items():
            new_value = entry.get().strip()
            if key == "BorrowerNames":
                latest_result.entities.BorrowerNames = [name.strip() for name in new_value.split(',') if name.strip()]
            elif key == "RidersPresent":
                logger.warning(f"Editing 'RidersPresent' as a plain string. Complex parsing not implemented for: {new_value}")
                setattr(latest_result.entities, key, new_value)
            elif key == "BorrowerSignaturesPresent":
                logger.warning(f"Editing 'BorrowerSignaturesPresent' as a plain string. Complex parsing not implemented for: {new_value}")
                setattr(latest_result.entities, key, new_value)
            elif hasattr(latest_result.entities, key):
                if key == "PageCount":
                    try:
                        latest_result.entities.PageCount = int(new_value) if new_value.isdigit() else None
                    except ValueError:
                        latest_result.entities.PageCount = None
                else:
                    setattr(latest_result.entities, key, new_value)
            else:
                logger.debug(f"Unknown entity key: {key} — cannot update model.")
        messagebox.showinfo("Edits Saved", "Your changes have been saved to the current analysis result.")


    def _copy_to_clipboard(self, text: str):
        """Copies the given text to the system clipboard."""
        try:
            self.clipboard_clear()
            self.clipboard_append(str(text))
            self.update_idletasks() # Ensure clipboard is updated immediately
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


    def _on_new_input_clicked(self):
        """
        Handles the 'Capture New Document' button click.
        This now only calls the callback to main.py, without destroying the window.
        """
        logger.info("ResultsWindow: 'Capture New Document' clicked. Not destroying window.")
        # Hide the window briefly while new capture is in progress
        self.withdraw()
        if self.on_new_input_callback:
            self.on_new_input_callback() # Call the main app's function to start new capture

    def _on_closing(self):
        """Handles the window close (X) button event. This will destroy the window."""
        logger.info("ResultsWindow: Window closed by user (X button). Destroying window.")
        self.destroy() # Destroy the window