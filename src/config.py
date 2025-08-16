import os
import logging

logger = logging.getLogger(__name__)

# --- Application Paths & Files ---
# Base directory for application data (e.g., for settings file)
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".mortgage_analyzer_app")
os.makedirs(APP_DATA_DIR, exist_ok=True) # Ensure the directory exists

# Path to the settings file
SETTINGS_FILE_PATH = os.path.join(APP_DATA_DIR, "settings.json")

# Name of the file where structured analysis results (JSON) will be saved.
OUTPUT_FILE_NAME = "extracted_mortgage_data.json"


# --- API Configuration ---
# OpenAI API key for GPT-4 analysis
# This will be initialized from environment variable or settings file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

# Validate that critical API keys are set (initial check, can be overridden by settings)
if not OPENAI_API_KEY:
    logger.critical("OPENAI_API_KEY environment variable not set. Please set it to proceed or use the settings dialog.")


# --- Application Behavior Configuration ---
# Hotkeys to trigger the screen capture.
# This will be loaded from settings or environment variables, or default.
HOTKEYS = os.getenv("HOTKEYS", 'ctrl+alt+m,ctrl+alt+a').split(',')
HOTKEYS = [h.strip() for h in HOTKEYS if h.strip()] # Clean up and remove empty strings


# --- UI Display Name Mapping ---
# Map long entity names to shorter, more UI-friendly names
ENTITY_DISPLAY_NAMES = {
    "DocumentType": "Doc Type",
    "BorrowerNames": "Borrowers",
    "BorrowerAddress": "Borrower Addr.",
    "BorrowerAlias": "Borrower Alias",
    "BorrowerWithRelationship": "Borrower Relation",
    "BorrowerWithTenantInformation": "Borrower Tenant Info",
    "LenderName": "Lender",
    "TrusteeName": "Trustee",
    "TrusteeAddress": "Trustee Addr.",
    "LoanAmount": "Loan Amt.",
    "PropertyAddress": "Prop. Addr.",
    "DocumentDate": "Doc Date",
    "MaturityDate": "Maturity Date",
    "APN_ParcelID": "APN / Parcel ID",
    "RecordingStampPresent": "Rec. Stamp?",
    "RecordingBook": "Rec. Book",
    "RecordingPage": "Rec. Page",
    "RecordingDocumentNumber": "Rec. Doc No.",
    "RecordingDate": "Rec. Date",
    "RecordingTime": "Rec. Time",
    "ReRecordingInformation": "Re-Rec. Info",
    "RecordingCost": "Rec. Cost",
    "BorrowerSignaturesPresent": "Borrower Signatures",
    "RidersPresent": "Riders",
    "InitialedChangesPresent": "Initialed Changes?",
    "MERS_RiderSelected": "MERS Rider Sel.?",
    "MERS_RiderSignedAttached": "MERS Rider Signed?",
    "MIN": "MIN",
    "LegalDescriptionPresent": "Legal Desc. Present?",
    "LegalDescriptionDetail": "Legal Desc. Detail"
}


# --- AI Model Configuration (if applicable for grammar correction or other local models) ---
GRAMMAR_CORRECTION_MODEL_NAME = "prithivida/grammar_error_correcter_v1"

# --- Logging Configuration (basic, detailed setup in utils/logging_config.py) ---
LOG_FILE_PATH = "app_log.log"
LOG_LEVEL = logging.INFO