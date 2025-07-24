import openai
import json
import logging
from typing import Dict, Any
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
            # Initialize the OpenAI client with the new syntax
            self.client = openai.OpenAI(api_key=openai_api_key)
            self.is_configured = True
            logger.info("AIAnalysisService initialized with new OpenAI client.")

    def analyze_mortgage_document(self, ocr_text: str) -> AnalysisResult:
        """
        Sends OCR text to GPT-4o to extract mortgage-related entities and generate a summary.
        The prompt is designed to adhere to the detailed extraction checklist.
        :param ocr_text: The raw text extracted from the document by OCR.
        :return: An AnalysisResult dataclass containing extracted entities, summary, and any errors.
        """
        if not self.is_configured:
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error="AIAnalysisService not configured due to missing API key.")
        if not ocr_text:
            return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error="No OCR text provided for AI analysis.")

        # --- Construct the detailed prompt based on the Extraction Checklist ---
        # This prompt guides GPT-4o to extract specific fields and format them as JSON.
        # It also asks for a concise summary.
        prompt = f"""
You are an intelligent document analysis agent specializing in Security Instruments, such as Mortgages and Deeds of Trust. Your task is to meticulously extract key information from the provided OCR text and then generate a concise summary.

**Instructions:**

1.  **Extract Key Entities:** From the "OCR Text" provided below, extract the following entities. Present them in a single JSON object.
    * If a field is not found in the text, or if it is not applicable (e.g., "Trustee Name" for a Mortgage document), use "N/A" or "Not Listed" as specified in the checklist hints, otherwise use an empty string if not specified.
    * For boolean-like fields (e.g., "Recording Stamp Present"), use "Yes" or "No".
    * For lists (e.g., "Borrower Names", "Riders Present"), use JSON arrays.

    **JSON Schema for Entities:**
    ```json
    {{
      "Document Type": "...",
      "Borrower Names": ["...", "..."],
      "Lender Name": "...",
      "Trustee Name": "...",
      "Trustee Address": "...",
      "Loan Amount": "...",
      "Property Address": "...",
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
      "Page Count": ...,
      "Missing Pages": "...",
      "Borrower Signatures Present": {{
          "Borrower Name 1": "Yes/No",
          "Borrower Name 2": "Yes/No"
      }},
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

    **Extraction Checklist Hints (for your reference, incorporate into extraction logic):**
    * **Document Type:** "Security Instrument" or "Title Policy".
    * **Recording Details:** Look for BK/PG, 10-12 digit Document No. (starts with current year or Title Order No.) on first or last 2 pages. For re-recording, use template: `DOCUMENT# (OR PAGE #); Re-recorded on ______in Book ______, Page_____ as Document/Instrument # ________.` Recording Cost: "Not Listed" if not present.
    * **Borrower(s) Name:** "BORROWER/MORTGAGOR/OWNER/TRUSTOR: PROPERTY OWNER TENANCY INFORMATION".
    * **Lender Name:** "LENDER/BENEFICIARY NAME".
    * **Document Date:** "NOTE DATE/DOCUMENT PREPARED DATE/MADE DATE/DATED DATE/DOCUMENT DATE", "the promissory note dated".
    * **Loan Amount:** "Note to pay Lender (LOAN AMOUNT)".
    * **Maturity Date:** "pay the debt full not later than (MATURITY DATE)". "N/A" for 2nd mortgage if not present.
    * **Property Address:** "the following described property located in (PROPERTY ADDRESS)" or "which currently has the address". Check borrower mailing (2nd address) on page 1 if missing on page 3.
    * **Trustee Name & Address:** If Deed of Trust, extract. If Mortgage, "N/A". Look for "TRUSTEE" and "TRUSTEE Address".
    * **Page Count:** Total pages in security instrument (don't count attached riders as separate). Specify missing pages like "Missing pages 5 – 8".
    * **Signatures of Parties:** For each listed borrower, "Yes/No".
    * **Riders Present:** List marked/selected riders. For each, "Yes/No" if signed copy attached. "N/A" if no riders marked.
    * **Initialed Changes:** For handwritten corrections on material fields (Loan amount, interest rate, payment amount, first payment due date, maturity date, deletion of mortgage covenants), "Yes/No" for borrower initials. "N/A" if no corrections. Disregard Notary section changes.
    * **MERS Rider & MIN:** "Yes/No" for MERS Rider selected/marked. If selected, "Yes/No" for signed attached. MIN always on first page if MERS is available.
    * **Legal Description:** "Yes/No" if present/attached. "legal description is missing" if missing. Look for "[EXHIBIT A or Legal Description]".

2.  **Generate Summary:** Write a concise, plain-English summary of the mortgage document. This summary should highlight the core purpose of the document, the parties involved, and key terms like the loan amount and property.

**Return your response as a single JSON object with two top-level keys:** `"entities"` (containing the JSON object from task 1) and `"summary"` (containing the string from task 2).

**OCR Text to Analyze:**
{ocr_text}
"""

        try:
            # Call OpenAI's ChatCompletion API using the new client syntax
            # Changed model to 'gpt-4o' which supports response_format={"type": "json_object"}
            response = self.client.chat.completions.create(
                model="gpt-4o", # Using gpt-4o for JSON output support and improved performance
                messages=[
                    {"role": "system", "content": "You are an expert document analysis agent for mortgage documents. You extract structured data and write concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3, # Lower temperature for more deterministic and factual extraction
                response_format={"type": "json_object"} # Ensure JSON output
            )

            # Access the content from the new response object structure
            result_content = response.choices[0].message.content
            logger.debug(f"Raw GPT response: {result_content[:500]}...")

            # Attempt to parse the JSON output from GPT
            parsed_data = json.loads(result_content)

            # Validate the top-level structure
            if "entities" not in parsed_data or "summary" not in parsed_data:
                logger.error(f"GPT response is malformed: missing 'entities' or 'summary' keys. Response: {result_content}")
                return AnalysisResult(entities=MortgageDocumentEntities(), summary="", error="Malformed AI response: missing entities or summary.")

            # Attempt to parse the entities into the structured dataclass
            entities_dict = parsed_data.get("entities", {})
            summary_text = parsed_data.get("summary", "No summary provided.")

            # Convert the raw dictionary from GPT into your structured dataclass
            # This requires careful mapping and handling of potential mismatches
            # The 'RidersPresent' list parsing is critical here.
            riders_list = []
            for r in entities_dict.get("Riders Present", []):
                if isinstance(r, dict):
                    # Ensure the key is 'SignedAttached' when creating Rider objects
                    # This handles potential variations from the LLM output
                    rider_name = r.get("Name")
                    signed_attached = r.get("SignedAttached") or r.get("Signed Attached") # Try both
                    if rider_name is not None and signed_attached is not None:
                        riders_list.append(Rider(Name=rider_name, SignedAttached=signed_attached))
                    else:
                        logger.warning(f"Skipping malformed rider entry: {r}")
                else:
                    logger.warning(f"Skipping non-dict rider entry: {r}")


            parsed_entities = MortgageDocumentEntities(
                DocumentType=entities_dict.get("Document Type", "N/A"),
                BorrowerNames=entities_dict.get("Borrower Names", []),
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
                PageCount=entities_dict.get("Page Count"), # Can be None if not found
                MissingPages=entities_dict.get("Missing Pages", "N/A"),
                BorrowerSignaturesPresent=entities_dict.get("Borrower Signatures Present", {}),
                RidersPresent=riders_list, # Use the correctly parsed list
                InitialedChangesPresent=entities_dict.get("Initialed Changes Present", "N/A"),
                MERS_RiderSelected=entities_dict.get("MERS Rider Selected", "No"),
                MERS_RiderSignedAttached=entities_dict.get("MERS Rider Signed Attached", "No"),
                MIN=entities_dict.get("MIN (Mortgage Identification Number)", "N/A"),
                LegalDescriptionPresent=entities_dict.get("Legal Description Present", "No"),
                LegalDescriptionDetail=entities_dict.get("Legal Description Detail", "N/A")
            )

            return AnalysisResult(entities=parsed_entities, summary=summary_text)

        # Catching the new OpenAI error types
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

