from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union

@dataclass
class ConfidenceValue:
    """
    Represents an extracted value along with its confidence score.
    Confidence score should be between 0.0 and 1.0.
    """
    value: Union[str, List[str], List[Any], None] = "N/A" # Using Any for RidersPresent flexibility
    confidence: float = 0.0

    def __str__(self):
        # Provides a string representation of just the value, for easier display
        if self.value is None or self.value == "N/A":
            return "N/A"
        if isinstance(self.value, list):
            # Special handling for lists for some fields
            return ", ".join(map(str, self.value)) if self.value else "N/A"
        return str(self.value)

    def __eq__(self, other):
        if isinstance(other, ConfidenceValue):
            return self.value == other.value and self.confidence == other.confidence
        return False

    def __hash__(self):
        return hash((str(self.value), self.confidence))


@dataclass
class Rider:
    Name: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    Present: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="No"))
    SignedAttached: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="No"))

@dataclass
class BorrowerEntry:
    Name: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    Alias: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value=[]))  # list of aliases or string
    Relationship: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    TenantInformation: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))

@dataclass
class MortgageDocumentEntities:
    DocumentType: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    Borrower: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value=[]))  # list of BorrowerEntry
    BorrowerAddress: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    LenderName: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    TrusteeName: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    TrusteeAddress: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    LoanAmount: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    PropertyAddress: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    DocumentDate: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    MaturityDate: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    APN_ParcelID: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    RecordingStampPresent: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="No"))
    RecordingBook: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    RecordingPage: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    RecordingDocumentNumber: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    RecordingDate: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    RecordingTime: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    ReRecordingInformation: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    RecordingCost: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="Not Listed"))
    RidersPresent: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value=[])) # List of Rider objects
    InitialedChangesPresent: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    MERS_RiderSelected: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="No"))
    MERS_RiderSignedAttached: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="No"))
    MIN: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))
    LegalDescriptionPresent: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="No"))
    LegalDescriptionDetail: ConfidenceValue = field(default_factory=lambda: ConfidenceValue(value="N/A"))

@dataclass
class AnalysisResult:
    entities: MortgageDocumentEntities
    summary: str
    error: Optional[str] = None
    document_id: str = "Unnamed Document"