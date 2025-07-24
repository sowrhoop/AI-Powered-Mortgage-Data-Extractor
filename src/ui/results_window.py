import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
from typing import Callable, Any, List, Dict
from models.document_entities import AnalysisResult, MortgageDocumentEntities, Rider # Import your structured models
from dataclasses import asdict # Import asdict for converting dataclass to dict

logger = logging.getLogger(__name__)

class ResultsWindow(tk.Toplevel):
    """
    A Toplevel Tkinter window to display the extracted entities and legal description
    from the mortgage document analysis. Provides copy functionality and
    an option to trigger a new document capture.
    """
    def __init__(self, parent: tk.Tk, all_analysis_results: List[AnalysisResult], on_new_input_callback: Callable[[], None]):
        """
        Initializes the ResultsWindow.
        :param parent: The parent Tkinter window (usually the hidden main root).
        :param all_analysis_results: A list of AnalysisResult objects containing entities and summary
                                     from all captured documents.
        :param on_new_input_callback: A callback function to execute when the user
                                      requests to capture a new document.
        """
        super().__init__(parent)
        logger.info("ResultsWindow: Initializing...")
        self.title("Mortgage Document Analysis Results")
        self.geometry("850x750") # Slightly larger window
        self.minsize(600, 500) # Minimum size for resizing

        self.all_analysis_results = all_analysis_results # Store the list of all results
        self.on_new_input_callback = on_new_input_callback

        self.protocol("WM_DELETE_WINDOW", self._on_closing) # Handle window close button

        # --- IMPORTANT: Ensure the window is always on top, centered, and gets focus ---
        self.attributes("-topmost", True) # Keep this window on top of others
        self.update_idletasks() # Ensure window dimensions are calculated before centering
        self._center_window() # Center the window on the screen

        self._create_widgets_layout() # Create static layout (notebook, frames, buttons)
        self._populate_content(self.all_analysis_results) # Populate with initial data
        logger.info("ResultsWindow: Widgets created and content populated.")

        # Explicitly bring to front and give focus after widgets are created
        self.lift() # Bring window to the top of the stacking order
        self.focus_force() # Force keyboard focus to this window
        self.update() # Force a redraw to ensure it's visible

        logger.info("Results window created and displayed (attempted to bring to front and focus).")

    def _center_window(self):
        """Centers the Toplevel window on the screen."""
        self.update_idletasks() # Update geometry to ensure correct width/height
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        self.geometry(f'+{x}+{y}')
        logger.debug(f"Results window centered at: ({x}, {y})")


    def _create_widgets_layout(self):
        """
        Creates the static layout of the results window (notebook, frames, buttons).
        This method is called only once during initialization.
        """
        # --- Notebook (Tabbed Interface) ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # --- Extracted Entities Tab ---
        self.entities_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.entities_frame, text="Extracted Entities")

        # Use a Canvas with Scrollbar for scrollable entity content
        self.entities_canvas = tk.Canvas(self.entities_frame, highlightthickness=0)
        self.entities_scrollbar = ttk.Scrollbar(self.entities_frame, orient="vertical", command=self.entities_canvas.yview)
        
        # Initial creation of scrollable_entities_frame - it will be recreated in _populate_content
        self.scrollable_entities_frame = ttk.Frame(self.entities_canvas) 
        self.entities_canvas_window = self.entities_canvas.create_window((0, 0), window=self.scrollable_entities_frame, anchor="nw")

        self.entities_canvas.configure(yscrollcommand=self.entities_scrollbar.set)

        self.entities_canvas.pack(side="left", fill="both", expand=True)
        self.entities_scrollbar.pack(side="right", fill="y")


        # --- Legal Description Tab (Replaces Summary Tab) ---
        self.legal_description_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.legal_description_frame, text="Legal Description")

        # Labels for Legal Description Present and Detail
        ttk.Label(self.legal_description_frame, text="Legal Description Present:", font=("Arial", 10, "bold")).pack(pady=(10, 0), padx=10, anchor="nw")
        self.legal_description_present_label = ttk.Label(self.legal_description_frame, text="N/A", font=("Arial", 10), wraplength=700, justify="left")
        self.legal_description_present_label.pack(pady=(2, 10), padx=10, anchor="nw")

        ttk.Label(self.legal_description_frame, text="Legal Description Detail:", font=("Arial", 10, "bold")).pack(pady=(10, 0), padx=10, anchor="nw")
        self.legal_description_detail_text_widget = tk.Text(self.legal_description_frame, height=15, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 10))
        self.legal_description_detail_text_widget.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

        # Copy button for Legal Description
        self.copy_legal_description_btn = ttk.Button(self.legal_description_frame, text="Copy Legal Description", command=self._copy_legal_description_to_clipboard)
        self.copy_legal_description_btn.pack(pady=5)


        # --- Control Buttons (remain the same) ---
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        copy_all_btn = ttk.Button(button_frame, text="Copy All Data (JSON)", command=self._copy_all_to_clipboard)
        copy_all_btn.pack(side=tk.LEFT, padx=5)

        new_input_btn = ttk.Button(button_frame, text="Capture New Document", command=self._on_new_input_clicked)
        new_input_btn.pack(side=tk.LEFT, padx=5)

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
        """
        Populates the UI widgets with data from the given list of AnalysisResult objects.
        This method clears existing content and repopulates by recreating the inner frame,
        and aggregates entities from all results.
        """
        logger.info(f"ResultsWindow: Populating content with {len(all_analysis_results)} analysis results.")
        self.all_analysis_results = all_analysis_results # Update the stored list of analysis results

        # --- Destroy and Recreate the scrollable_entities_frame ---
        if self.scrollable_entities_frame:
            self.scrollable_entities_frame.destroy()
            logger.debug("ResultsWindow: Destroyed old scrollable_entities_frame.")
        
        # Recreate the frame inside the canvas
        self.scrollable_entities_frame = ttk.Frame(self.entities_canvas)
        self.entities_canvas_window = self.entities_canvas.create_window((0, 0), window=self.scrollable_entities_frame, anchor="nw")
        
        # Re-bind the configure event for the new frame
        self.scrollable_entities_frame.bind(
            "<Configure>",
            lambda e: self.entities_canvas.configure(scrollregion=self.entities_canvas.bbox("all"))
        )
        logger.debug("ResultsWindow: Recreated new scrollable_entities_frame and re-bound.")
        # --- End Destroy and Recreate ---

        # --- Aggregate Entities from all results ---
        combined_entities: Dict[str, Any] = {}
        
        # Define a consistent order for display, including the new field
        display_order = [
            "DocumentType", "BorrowerNames", "BorrowerRelationships", "LenderName", "TrusteeName", "TrusteeAddress",
            "LoanAmount", "PropertyAddress", "DocumentDate", "MaturityDate", "APN_ParcelID",
            "RecordingStampPresent", "RecordingBook", "RecordingPage", "RecordingDocumentNumber",
            "RecordingDate", "RecordingTime", "ReRecordingInformation", "RecordingCost",
            "PageCount", "MissingPages", "BorrowerSignaturesPresent", "RidersPresent",
            "InitialedChangesPresent", "MERS_RiderSelected", "MERS_RiderSignedAttached",
            "MIN", "LegalDescriptionPresent", "LegalDescriptionDetail"
        ]

        # Iterate through results from oldest to newest to prioritize later updates for single values
        for result in all_analysis_results:
            if result.error or not result.entities:
                continue # Skip results with errors or no entities

            current_entities_dict = asdict(result.entities)

            for key in display_order: # Iterate through the defined order to ensure all fields are considered
                current_value = current_entities_dict.get(key)
                
                if current_value is None: # Treat None as not found
                    continue

                if key == "BorrowerNames":
                    # Combine unique borrower names
                    existing_names = set(combined_entities.get(key, []))
                    if isinstance(current_value, list):
                        for name in current_value:
                            existing_names.add(name)
                    combined_entities[key] = sorted(list(existing_names)) # Keep sorted for consistency
                elif key == "BorrowerRelationships": # Handle BorrowerRelationships
                    # Merge dictionaries, latest values override
                    existing_relationships = combined_entities.get(key, {})
                    if isinstance(current_value, dict):
                        existing_relationships.update(current_value)
                    combined_entities[key] = existing_relationships
                elif key == "RidersPresent":
                    # Combine unique riders based on name
                    existing_riders = {r['Name']: r for r in combined_entities.get(key, [])}
                    if isinstance(current_value, list):
                        for rider_dict in current_value:
                            if isinstance(rider_dict, dict) and 'Name' in rider_dict:
                                existing_riders[rider_dict['Name']] = rider_dict # Overwrite if name exists (latest status)
                    combined_entities[key] = list(existing_riders.values())
                elif key == "BorrowerSignaturesPresent":
                    # Merge dictionaries, latest values override
                    existing_signatures = combined_entities.get(key, {})
                    if isinstance(current_value, dict):
                        existing_signatures.update(current_value)
                    combined_entities[key] = existing_signatures
                elif isinstance(current_value, (str, int, float)) and \
                     str(current_value).strip().lower() not in ["n/a", "not listed", ""]:
                    # For single values, if the current value is meaningful, update it
                    combined_entities[key] = current_value
                elif key not in combined_entities: # If key not set yet, and current_value is "N/A" etc., still set it once
                    combined_entities[key] = current_value # Set it, but might be overwritten by a meaningful value later


        # Populate entities in the UI from the combined_entities
        if combined_entities:
            for key in display_order: # Use display_order to ensure consistent ordering in UI
                value = combined_entities.get(key)
                
                formatted_value = ""
                if key == "BorrowerNames": # Special handling for BorrowerNames to include relationships
                    borrower_names = combined_entities.get("BorrowerNames", [])
                    borrower_relationships = combined_entities.get("BorrowerRelationships", {})
                    
                    combined_borrower_info = []
                    for name in borrower_names:
                        relationship = borrower_relationships.get(name, "")
                        if relationship:
                            combined_borrower_info.append(f"{name} ({relationship})")
                        else:
                            combined_borrower_info.append(name)
                    formatted_value = ", ".join(combined_borrower_info)
                    
                    # If BorrowerNames is handled, skip the separate BorrowerRelationships entry
                    if key == "BorrowerNames" and "BorrowerRelationships" in display_order:
                        # Find and remove "BorrowerRelationships" from display_order for this iteration
                        # This is a bit tricky with direct iteration, a better way is to skip adding it
                        # if BorrowerNames is being processed.
                        pass # We will handle this by checking 'key' below
                elif key == "BorrowerRelationships": # Skip this if already handled by BorrowerNames
                    continue 
                elif isinstance(value, list):
                    if key == "RidersPresent":
                        formatted_rider_values = []
                        for r_dict in value:
                            if isinstance(r_dict, dict):
                                name = r_dict.get('Name', 'N/A')
                                signed_attached = r_dict.get('SignedAttached', 'N/A')
                                formatted_rider_values.append(f"- {name} (Signed: {signed_attached})")
                        formatted_value = "\n".join(formatted_rider_values)
                    else:
                        formatted_value = ", ".join(map(str, value))
                elif isinstance(value, dict):
                    formatted_value = "\n".join([f"{k}: {v}" for k, v in value.items()])
                elif value is None:
                    formatted_value = "N/A"
                else:
                    formatted_value = str(value)

                display_key = key.replace("_", " ").replace("ID", " ID").replace("APN", "APN").replace("MIN", "MIN").title()
                if key == "MIN":
                    display_key = "MIN (Mortgage Identification Number)"
                
                # Only add the row if it's not "BorrowerRelationships" or if it's "BorrowerNames" (which now includes relationships)
                if key != "BorrowerRelationships":
                    self._add_entity_row(self.scrollable_entities_frame, display_key, formatted_value)
                    logger.debug(f"ResultsWindow: Added row for {display_key}: {formatted_value[:50]}...")
        else:
            ttk.Label(self.scrollable_entities_frame, text="Ready for new document capture. Please use the hotkey to select an area.", foreground="gray").pack(pady=20)

        # After all content is added, force updates and reconfigure scroll region
        self.scrollable_entities_frame.update_idletasks()
        self.entities_canvas.configure(scrollregion=self.entities_canvas.bbox("all"))
        self.entities_canvas.yview_moveto(0) # Scroll to the top to show new content first

        # Populate Legal Description tab (from the latest document in the list)
        latest_result = self.all_analysis_results[-1] if self.all_analysis_results else None
        if latest_result and latest_result.entities:
            legal_present = latest_result.entities.LegalDescriptionPresent
            legal_detail = latest_result.entities.LegalDescriptionDetail
        else:
            legal_present = "N/A"
            legal_detail = "No legal description available from latest document. Ready for new capture."

        self.legal_description_present_label.config(text=legal_present)
        
        self.legal_description_detail_text_widget.config(state=tk.NORMAL)
        self.legal_description_detail_text_widget.delete(1.0, tk.END) # Clear existing text
        self.legal_description_detail_text_widget.insert(tk.END, legal_detail)
        self.legal_description_detail_text_widget.config(state=tk.DISABLED)


    def update_data(self, new_all_analysis_results: List[AnalysisResult]):
        """
        Updates the content of the ResultsWindow with new analysis data.
        :param new_all_analysis_results: The updated list of AnalysisResult objects to display.
        """
        logger.info("ResultsWindow: Updating data with new analysis result list.")
        self._populate_content(new_all_analysis_results)
        self.lift() # Bring to front
        self.focus_force() # Force focus
        self.update() # Force redraw

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


    def _add_entity_row(self, parent_frame: ttk.Frame, key: str, value: str):
        """
        Adds a single row for an extracted entity (Key: Value) with a Copy button.
        :param parent_frame: The frame to which this row will be added.
        :param key: The name of the entity.
        :param value: The extracted value of the entity.
        """
        row_frame = ttk.Frame(parent_frame)
        row_frame.pack(fill=tk.X, padx=10, pady=2)

        # Label for the entity key (bold for emphasis)
        key_label = ttk.Label(row_frame, text=f"{key}:", font=("Arial", 9, "bold"), width=30, anchor="w")
        key_label.pack(side=tk.LEFT, padx=(0, 5))

        # Label for the entity value (wraps text if too long)
        value_label = ttk.Label(row_frame, text=value, wraplength=450, justify="left", anchor="w")
        value_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Copy button for individual entity
        copy_btn = ttk.Button(row_frame, text="Copy", command=lambda v=value: self._copy_to_clipboard(v), width=8)
        copy_btn.pack(side=tk.RIGHT)

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

    def _copy_all_to_clipboard(self):
        """Copies the entire analysis result (entities and summary) as JSON to the clipboard."""
        try:
            # Convert the list of AnalysisResult dataclasses to a list of dictionaries for JSON serialization
            full_content_list_dict = [asdict(res) for res in self.all_analysis_results]
            full_content_json = json.dumps(full_content_list_dict, indent=2)

            self.clipboard_clear()
            self.clipboard_append(full_content_json)
            self.update_idletasks()
            messagebox.showinfo("Copied", "All extracted data (JSON) copied to clipboard!")
            logger.info("Copied all extracted data (JSON) to clipboard.")
        except Exception as e:
            messagebox.showerror("Copy Error", f"Failed to copy all data: {e}")
            logger.error(f"Error copying all data to clipboard: {e}", exc_info=True)

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
