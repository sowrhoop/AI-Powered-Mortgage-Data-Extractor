import os
import logging

logger = logging.getLogger(__name__)

APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".ascendant_vision_ai_platform")
os.makedirs(APP_DATA_DIR, exist_ok=True)

SETTINGS_FILE_PATH = os.path.join(APP_DATA_DIR, "settings.json")
OUTPUT_FILE_NAME = "ascendant_vision_ai_results.json"

# Do not read any values from environment variables. Defaults are internal,
# and user configuration is persisted in settings.json handled by the app.
OPENAI_API_KEY = ""

# Default hotkeys used unless overridden via settings.json
HOTKEYS = ['ctrl+alt+m', 'ctrl+alt+a']

ENTITY_DISPLAY_NAMES = {
    "DocumentType": "Doc Type",
    "Borrower": "Borrowers",
    "BorrowerAddress": "Borrower Addr.",
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
    "RidersPresent": "Checked Riders",
    "InitialedChangesPresent": "Initialed Changes?",
    "MERS_RiderSelected": "MERS Rider Sel.?",
    "MERS_RiderSignedAttached": "MERS Rider Signed?",
    "MIN": "MIN",
    "LegalDescriptionPresent": "Legal Desc. Present?",
    "LegalDescriptionDetail": "Legal Desc. Detail"
}

# Entity keys that represent currency/monetary amounts. Used for consistent formatting
# and normalization across the app (always keep two decimals).
MONEY_FIELDS = [
    "LoanAmount",
    "RecordingCost",
]

# Mapping of US state/territory postal abbreviations to full names for
# address normalization when required (e.g., PropertyAddress).
US_STATE_ABBR_TO_NAME = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
    "GU": "Guam",
    "VI": "U.S. Virgin Islands",
    "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

RIDER_ALLOWLIST = [
    "Adjustable Rate Rider",
    "1-4 Family Rider",
    "Condominium Rider",
    "Planned Unit Development Rider",
    "Second Home Rider",
    "V.A. Rider",
    "Biweekly Payment Rider",
]

RIDER_ALIASES = {
    "adjustable rate rider": "Adjustable Rate Rider",
    "arm rider": "Adjustable Rate Rider",

    "1-4 family rider": "1-4 Family Rider",
    "1 to 4 family rider": "1-4 Family Rider",
    "one-to-four family rider": "1-4 Family Rider",
    "one to four family rider": "1-4 Family Rider",

    "condominium rider": "Condominium Rider",
    "condo rider": "Condominium Rider",

    "planned unit development rider": "Planned Unit Development Rider",
    "planned unit dev rider": "Planned Unit Development Rider",
    "pud rider": "Planned Unit Development Rider",

    "second home rider": "Second Home Rider",

    "v.a. rider": "V.A. Rider",
    "va rider": "V.A. Rider",
    "v a rider": "V.A. Rider",

    "biweekly payment rider": "Biweekly Payment Rider",
    "bi-weekly payment rider": "Biweekly Payment Rider",
    "bi weekly payment rider": "Biweekly Payment Rider",

    # Ambiguous labels to ignore
    "other(s) [specify]": "",
    "others": "",
    "other": "",
}

GRAMMAR_CORRECTION_MODEL_NAME = "prithivida/grammar_error_correcter_v1"

LOG_FILE_PATH = "ascendant_vision_ai_platform.log"
LOG_LEVEL = logging.INFO

# OpenAI model and request settings
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TIMEOUT = 60.0

# Minimum confidence required for UI display of any entity/value
UI_CONFIDENCE_MIN = 0.9