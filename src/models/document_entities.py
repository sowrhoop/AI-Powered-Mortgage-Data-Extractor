from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class Rider:
    """Represents a rider attached to the mortgage document."""
    Name: str
    SignedAttached: str # "Yes" or "No"

@dataclass
class MortgageDocumentEntities:
    """
    A dataclass to hold all extracted entities from a mortgage document,
    following the detailed extraction checklist.
    Default values are set to "N/A", "No", or empty lists/dicts to ensure
    all fields are always present, even if not found by the AI.
    """
    DocumentType: str = "N/A"
    BorrowerNames: List[str] = field(default_factory=list) # List of borrower full names
    LenderName: str = "N/A"
    TrusteeName: str = "N/A" # "N/A" if Mortgage
    TrusteeAddress: str = "N/A" # "N/A" if Mortgage
    LoanAmount: str = "N/A"
    PropertyAddress: str = "N/A"
    DocumentDate: str = "N/A"
    MaturityDate: str = "N/A"
    APN_ParcelID: str = "N/A"
    RecordingStampPresent: str = "No" # "Yes" or "No"
    RecordingBook: str = "N/A"
    RecordingPage: str = "N/A"
    RecordingDocumentNumber: str = "N/A"
    RecordingDate: str = "N/A"
    RecordingTime: str = "N/A"
    ReRecordingInformation: str = "N/A" # Template: DOCUMENT# (OR PAGE #); Re-recorded on ______in Book ______, Page_____ as Document/Instrument # ________.`
    RecordingCost: str = "Not Listed"
    PageCount: Optional[int] = None # Total number of pages
    MissingPages: str = "N/A" # e.g., "Missing pages 5 – 8" or "N/A"
    BorrowerSignaturesPresent: Dict[str, str] = field(default_factory=dict) # e.g., {"John Doe": "Yes", "Jane Doe": "No"}
    RidersPresent: List[Rider] = field(default_factory=list) # List of Rider objects
    InitialedChangesPresent: str = "N/A" # "Yes" or "No"
    MERS_RiderSelected: str = "No" # "Yes" or "No"
    MERS_RiderSignedAttached: str = "No" # "Yes" or "No"
    MIN: str = "N/A" # Mortgage Identification Number
    LegalDescriptionPresent: str = "No" # "Yes" or "No"
    LegalDescriptionDetail: str = "N/A" # "Legal Description available" or "legal description is missing"

@dataclass
class AnalysisResult:
    """
    A dataclass to encapsulate the full result of the document analysis,
    including the structured entities, the summary, and any error messages.
    """
    entities: MortgageDocumentEntities
    summary: str
    error: Optional[str] = None # To hold any error messages during analysis
    document_id: str = "Unnamed Document" # New field to identify each document/screenshot
