import openai
import json
import logging
from typing import Dict, Any, Optional
from models.document_entities import AnalysisResult, MortgageDocumentEntities, Rider # Import your structured models
 
logger = logging.getLogger(__name__)
 
class AIAnalysisService:
    """
    Handles AI-powered document analysis using OpenAI's GPT models.
    Extracts structured entities and generates a summary from OCR text.
    """
    def __init__(self, openai_api_key: str):
        """
        Initializes the AIAnalysisService with the OpenAI API key.
        :param openai_api_key: Your OpenAI API key.
        """
        if not openai_api_key:
            logger.error("OpenAI API key is missing. AI analysis will not function.")
            self.is_configured = False
        else:
            # Initialize the OpenAI client for asynchronous operations
            self.client = openai.AsyncOpenAI(api_key=openai_api_key)
            self.is_configured = True
            logger.info("AIAnalysisService initialized with new AsyncOpenAI client.")
 
    async def analyze_mortgage_document(self, ocr_text: str, base64_image: Optional[str] = None) -> AnalysisResult:
        """
        Sends a Base64 image to GPT-4o to perform OCR, extract mortgage-related entities,
        and generate a concise summary. The prompt is designed for efficient, accurate extraction
        from the image, including contextual validation.
        
        :param ocr_text: This parameter is no longer used as OCR is handled by OpenAI.
                         It is kept for compatibility but can be an empty string.
        :param base64_image: The Base64 encoded string of the cropped image for multimodal analysis.
        :return: An AnalysisResult dataclass containing extracted entities, summary, and any errors.
        """
        if not self.is_configured:
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error="AIAnalysisService not configured due to missing API key.")
        
        # Ensure that an image is provided since OCR and extraction are now handled by AI
        if not base64_image:
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error="No image provided for AI analysis (OCR and extraction).")
 
        # Construct the detailed prompt for efficient extraction
        # The prompt explicitly tells GPT-4o to perform OCR from the image.
        prompt_text = """
**Task:** Perform OCR from the provided image of a Security Instrument (Mortgage or Deed of Trust), extract specific entities, and generate a concise summary.

**Output Format:** Return a single JSON object with two top-level keys: `"entities"` (containing extracted data) and `"summary"` (containing the summary string).

**1. Entities Extraction (JSON Schema & Rules):**
Extract the following entities. If a field is not found or not applicable, use "N/A", "Not Listed", or an empty list/dict as specified. Use "Yes" or "No" for boolean fields.

```json
{{
  "Document Type": "...",
  "Borrower Names": ["...", "..."],
  "Borrower Alias": ["...", "..."],
  "Borrower With Relationship": ["...", "..."],(extract only borrower with relationship information)
  "Borrower with Tenant Information": ["...", "..."],(extract only borrower with tenant information)
  "Borrower Address":"...",(currently residing at)
  "Lender Name": "...",
  "Trustee Name": "...",
  "Trustee Address": "...",(Trustee Address is)
  "Loan Amount": "...",
  "Property Address": "...", do not take Borrower Address as Property Address" (which currently has the address or check in the Legal Description Detail)
  "Document Date": "...",
  "Maturity Date": "...",
  "APN / Parcel ID": "...",
  "Recording Stamp Present": "Yes/No",
  "Recording Book": "...",
  "Recording Page": "...",
  "Recording Document Number": "...",
  "Recording Date": "...",
  "Recording Time": "...",
  "Re-recording Information": "...",
  "Recording Cost": "...",
  "Borrower Signatures Present": {{
      "Borrower Name 1": "Yes/No",
      "Borrower Name 2": "Yes/No"
  }},(borrower signatures present borrower names is yes then include in the analysis)
  "Riders Present": [
    {{ "Name": "...", "SignedAttached": "Yes/No" }}
  ],
  "Initialed Changes Present": "Yes/No",
  "MERS Rider Selected": "Yes/No",
  "MERS Rider Signed Attached": "Yes/No",
  "MIN (Mortgage Identification Number)": "...",
  "Legal Description Present": "Yes/No",
  "Legal Description Detail": "..."
}}
```

**Extraction Guidelines:**
* **Document Type:** "Security Instrument" or "Title Policy".
* **Recording Details:** Look for BK/PG, 10-12 digit Document No. (starts with current year or Title Order No.) on first or last 2 pages. For re-recording, use template: `DOCUMENT# (OR PAGE #); Re-recorded on ______in Book ______, Page_____ as Document/Instrument # ________.` Recording Cost: "Not Listed" if not present.
* **Borrower(s) Name:** "BORROWER/MORTGAGOR/OWNER/TRUSTOR: PROPERTY OWNER TENANCY INFORMATION."
* **Borrower Alias:** "BORROWER ALIAS INFORMATION."
* **Borrower With Relationship:** "BORROWER'S RELATIONSHIP INFORMATION. RETURN ONLY RELATIONSHIP INFORMATION."
* **Borrower with Tenant Information:** "BORROWER WITH TENANT INFORMATION."
* **Borrower Address"** "currently residing at from borrower address"
* **Lender Name:** "LENDER/BENEFICIARY NAME".
* **Document Date:** "NOTE DATE/DOCUMENT PREPARED DATE/MADE DATE/DATED DATE/DOCUMENT DATE", "the promissory note dated".
* **Loan Amount:** "Note to pay Lender (LOAN AMOUNT)".
* **Maturity Date:** "pay the debt full not later than (MATURITY DATE)". "N/A" for 2nd mortgage if not present.
* **Property Address (Guardrail):** "which currently has the address" or Prioritize the address explicitly stated in the "Transfer of Rights" or "Legal Description" sections. If no specific section is indicated, use the most prominent or complete address from the image, do not take Borrower Address as Property Address" (which currently has the address or check in the Legal Description Detail).
* **Trustee Name & Address:** If Deed of Trust, extract. If Mortgage, "N/A". Look for "TRUSTEE" and "TRUSTEE Address".
* **Borrower Signatures Present:** For each borrower, "Yes/No" if signature is present. If multiple borrowers, list each with their signature status (e.g., "Brad Johnson: Yes, Kimberly Kliethermes: No").
* **Riders Present:** List marked/selected riders. For each, "Yes/No" if signed copy attached. "N/A" if no riders marked.
* **Initialed Changes:** For handwritten corrections on material fields (Loan amount, interest rate, payment amount, first payment due date, maturity date, deletion of mortgage covenants), "Yes/No" for borrower initials. "N/A" if no corrections. Disregard Notary section changes.
* **MERS Rider & MIN:** "Yes/No" for MERS Rider selected/marked. If selected, "Yes/No" for signed attached. MIN always on first page if MERS is available.
* **Legal Description:** "Yes/No" if present/attached. "legal description is missing" if missing. Look for "[EXHIBIT A or Legal Description]".

**2. Summary Generation:**
Provide a concise, plain-English summary of the mortgage document. Highlight its core purpose, involved parties, and key terms (e.g., loan amount, property).
"""
        messages = [
            {"role": "system", "content": "You are an expert document analysis agent for mortgage documents. You perform OCR from images, extract structured data, and write concise summaries. Focus on efficiency and accuracy."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
        logger.debug("Prepared AI analysis request with Base64 image and concise prompt.")
 
        try:
            # Call OpenAI's ChatCompletion API with a timeout
            # A timeout of 60 seconds is chosen to allow for potential retries by the OpenAI client
            # while preventing indefinite hangs. Adjust as needed based on typical response times.
            response = await self.client.chat.completions.create(
                model="gpt-4o", # Using gpt-4o for JSON output support and improved performance
                messages=messages,
                temperature=0.5, # Lower temperature for more deterministic and factual extraction
                response_format={"type": "json_object"}, # Ensure JSON output
                timeout=60.0 # Set a timeout for the API call in seconds
            )
 
            # Access the content from the response object
            result_content = response.choices[0].message.content
            logger.debug(f"Raw GPT response: {result_content}...")
 
            # Attempt to parse the JSON output from GPT
            parsed_data = json.loads(result_content)

            logger.info(f"Parsed GPT response: {parsed_data}")
            # Validate the top-level structure
            if "entities" not in parsed_data or "summary" not in parsed_data:
                logger.error(f"GPT response is malformed: missing 'entities' or 'summary' keys. Response: {result_content}")
                return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error="Malformed AI response: missing entities or summary.")
 
            # Parse entities and summary
            entities_dict = parsed_data.get("entities", {})
            summary_text = parsed_data.get("summary", "No summary provided.")
 
            # Convert the raw dictionary from GPT into the structured dataclass
            # This requires careful mapping and handling of potential mismatches
            riders_list = []
            for r in entities_dict.get("Riders Present", []):
                if isinstance(r, dict):
                    # Ensure the key is 'SignedAttached' when creating Rider objects
                    # This handles potential variations from the LLM output
                    rider_name = r.get("Name")
                    signed_attached = r.get("SignedAttached") or r.get("Signed Attached") # Try both common keys
                    if rider_name is not None and signed_attached is not None:
                        riders_list.append(Rider(Name=rider_name, SignedAttached=signed_attached))
                    else:
                        logger.warning(f"Skipping malformed rider entry: {r}")
                else:
                    logger.warning(f"Skipping non-dict rider entry: {r}")
 
            parsed_entities = MortgageDocumentEntities(
                DocumentType=entities_dict.get("Document Type", "N/A"),
                BorrowerNames=entities_dict.get("Borrower Names", []),
                BorrowerAlias=entities_dict.get("Borrower Alias", []),
                BorrowerWithRelationship=entities_dict.get("Borrower With Relationship", []),
                BorrowerWithTenantInformation=entities_dict.get("Borrower with Tenant Information", []),
                BorrowerAddress=entities_dict.get("Borrower Address", "N/A"),
                LenderName=entities_dict.get("Lender Name", "N/A"),
                TrusteeName=entities_dict.get("Trustee Name", "N/A"),
                TrusteeAddress=entities_dict.get("Trustee Address", "N/A"),
                LoanAmount=entities_dict.get("Loan Amount", "N/A"),
                PropertyAddress=entities_dict.get("Property Address", "N/A"),
                DocumentDate=entities_dict.get("Document Date", "N/A"),
                MaturityDate=entities_dict.get("Maturity Date", "N/A"),
                APN_ParcelID=entities_dict.get("APN / Parcel ID", "N/A"),
                RecordingStampPresent=entities_dict.get("Recording Stamp Present", "No"),
                RecordingBook=entities_dict.get("Recording Book", "N/A"),
                RecordingPage=entities_dict.get("Recording Page", "N/A"),
                RecordingDocumentNumber=entities_dict.get("Recording Document Number", "N/A"),
                RecordingDate=entities_dict.get("Recording Date", "N/A"),
                RecordingTime=entities_dict.get("Recording Time", "N/A"),
                ReRecordingInformation=entities_dict.get("Re-recording Information", "N/A"),
                RecordingCost=entities_dict.get("Recording Cost", "Not Listed"),
                BorrowerSignaturesPresent=entities_dict.get("Borrower Signatures Present", {}),
                RidersPresent=riders_list, # Use the correctly parsed list
                InitialedChangesPresent=entities_dict.get("Initialed Changes Present", "N/A"),
                MERS_RiderSelected=entities_dict.get("MERS Rider Selected", "No"),
                MERS_RiderSignedAttached=entities_dict.get("MERS Rider Signed Attached", "No"),
                MIN=entities_dict.get("MIN (Mortgage Identification Number)", "N/A"),
                LegalDescriptionPresent=entities_dict.get("Legal Description Present", "No"),
                LegalDescriptionDetail=entities_dict.get("Legal Description Detail", "N/A")
            )
            logger.info(f"Parsed entities: {parsed_entities}")
            return AnalysisResult(entities=parsed_entities, summary=summary_text)
 
        # Catching and logging specific OpenAI error types
        except openai.APITimeoutError as e: # Catch timeout explicitly
            logger.error(f"OpenAI API request timed out: {e}", exc_info=True)
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=f"OpenAI API request timed out: {e}")
        except openai.APIConnectionError as e:
            logger.error(f"OpenAI API connection error: {e}", exc_info=True)
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=f"OpenAI API connection error: {e}")
        except openai.RateLimitError as e:
            logger.error(f"OpenAI API rate limit exceeded: {e}", exc_info=True)
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=f"OpenAI API rate limit exceeded: {e}")
        except openai.APIStatusError as e: # Catches other API errors like 400, 401, 403, 404, 429, 500
            logger.error(f"OpenAI API status error (Status: {e.status_code}, Response: {e.response}): {e}", exc_info=True)
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=f"OpenAI API error (Status: {e.status_code}): {e.response}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from GPT response: {e}. Raw response: {result_content}", exc_info=True)
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=f"AI response was not valid JSON: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during AI analysis: {e}", exc_info=True)
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error=f"Unexpected error during AI analysis: {e}")