import time
import logging
import http.client
import urllib.parse
import json
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient # Although not directly used for 'read' API, good to keep for context

logger = logging.getLogger(__name__)

class OCRService:
    """
    Handles Optical Character Recognition (OCR) using Azure Vision API.
    """
    def __init__(self, endpoint: str, api_key: str):
        """
        Initializes the OCRService with Azure Vision API credentials.
        :param endpoint: The Azure Vision API endpoint.
        :param api_key: The Azure Vision API subscription key.
        """
        if not endpoint or not api_key:
            logger.error("Azure Vision API endpoint or key is missing. OCR will not function.")
            self.is_configured = False
        else:
            # Clean the endpoint for http.client.HTTPSConnection
            self.endpoint_host = endpoint.replace("https://", "").replace("/", "")
            self.api_key = api_key
            self.is_configured = True
            logger.info(f"OCRService initialized for endpoint: {self.endpoint_host}")

    def perform_ocr(self, image_bytes: bytes, language: str = 'en') -> str:
        """
        Sends image bytes to Azure Vision API for OCR and retrieves the extracted text.
        Includes retry logic for API calls.
        :param image_bytes: The image content as bytes (e.g., PNG, JPEG).
        :param language: The language for OCR (e.g., 'en' for English).
        :return: The extracted text as a string, or an empty string if OCR fails.
        """
        if not self.is_configured:
            logger.error("OCRService not configured. Cannot perform OCR.")
            return ""

        if not image_bytes:
            logger.warning("No image bytes provided for OCR.")
            return ""

        headers = {
            'Content-Type': 'application/octet-stream',
            'Ocp-Apim-Subscription-Key': self.api_key,
        }
        params = urllib.parse.urlencode({'language': language})
        ocr_text = ""
        operation_location = None

        # --- Step 1: Submit image for analysis ---
        try:
            conn = http.client.HTTPSConnection(self.endpoint_host)
            # The path for the 'read' API (v3.2 is common, check Azure docs for latest)
            api_path = f"/vision/v3.2/read/analyze?{params}"
            logger.debug(f"Submitting image to Azure OCR: {self.endpoint_host}{api_path}")
            conn.request("POST", api_path, image_bytes, headers)
            response = conn.getresponse()
            
            if response.status == 202: # Accepted, analysis is in progress
                operation_location = response.headers.get("Operation-Location")
                logger.info(f"Azure OCR analysis initiated. Operation-Location: {operation_location}")
            else:
                error_response = response.read().decode()
                logger.error(f"Azure OCR submission failed with status {response.status}: {error_response}")
                return ""
            conn.close()

            if not operation_location:
                logger.error("Azure OCR submission did not return an Operation-Location header.")
                return ""

            # Extract operation ID from the URL
            operation_id = operation_location.split("/")[-1]

        except Exception as e:
            logger.error(f"Error submitting image to Azure OCR: {e}", exc_info=True)
            return ""

        # --- Step 2: Poll for analysis results ---
        max_retries = 10
        retry_delay_seconds = 2
        for i in range(max_retries):
            time.sleep(retry_delay_seconds) # Wait before polling
            try:
                conn = http.client.HTTPSConnection(self.endpoint_host)
                result_path = f"/vision/v3.2/read/analyzeResults/{operation_id}"
                logger.debug(f"Polling Azure OCR results ({i+1}/{max_retries}): {self.endpoint_host}{result_path}")
                conn.request("GET", result_path, None, headers)
                result_response = conn.getresponse()
                result_json = json.loads(result_response.read().decode())
                conn.close()

                status = result_json.get("status")
                if status == "succeeded":
                    # Concatenate text from all lines and pages
                    for page in result_json.get("analyzeResult", {}).get("readResults", []):
                        for line in page.get("lines", []):
                            ocr_text += line.get("text", "") + " "
                    logger.info("Azure OCR succeeded.")
                    return ocr_text.strip() # Remove leading/trailing whitespace

                elif status == "failed":
                    logger.error(f"Azure OCR analysis failed: {result_json.get('error', 'No error details')}")
                    return ""
                elif status == "running" or status == "notStarted":
                    logger.info(f"Azure OCR still processing... Retrying in {retry_delay_seconds} seconds.")
                    # Continue loop to retry
                else:
                    logger.warning(f"Unexpected Azure OCR status: {status}. Response: {result_json}")
                    return ""

            except Exception as e:
                logger.error(f"Error polling Azure OCR results: {e}", exc_info=True)
                return ""

        logger.error(f"Azure OCR took too long to complete after {max_retries} retries.")
        return ""


