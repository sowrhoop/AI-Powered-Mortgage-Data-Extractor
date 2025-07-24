import os
import logging

logger = logging.getLogger(__name__)

# --- API Configuration ---
# Azure Vision API endpoint and key for OCR
# Loaded from environment variables for security.
# If not found, a ValueError is raised, prompting the user to set them.
AZURE_VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT", "https://xtvision.cognitiveservices.azure.com")
AZURE_VISION_KEY = os.getenv("AZURE_VISION_KEY")

# OpenAI API key for GPT-4 analysis
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate that critical API keys are set
if not AZURE_VISION_KEY:
    logger.critical("AZURE_VISION_KEY environment variable not set. Please set it to proceed.")
    # In a production app, you might want to exit or disable features here
    # For now, we'll let the app try to run but log a critical error.
if not OPENAI_API_KEY:
    logger.critical("OPENAI_API_KEY environment variable not set. Please set it to proceed.")

# --- Application Behavior Configuration ---
# Hotkeys to trigger the screen capture.
# Users can press any of these combinations.
HOTKEYS = ['ctrl+alt+m', 'ctrl+alt+a']

# Name of the file where structured analysis results (JSON) will be saved.
OUTPUT_FILE_NAME = "extracted_mortgage_data.json"

# --- AI Model Configuration (if applicable for grammar correction or other local models) ---
# Example: Model name for a local grammar correction transformer model
# (Note: The grammar correction part from original code is not fully integrated
# into this refactored version by default, but this variable is kept for future use)
GRAMMAR_CORRECTION_MODEL_NAME = "prithivida/grammar_error_correcter_v1"

# --- Logging Configuration (basic, detailed setup in utils/logging_config.py) ---
# This is just for reference; actual logging setup is in logging_config.py
LOG_FILE_PATH = "app_log.log"
LOG_LEVEL = logging.INFO # Set to logging.DEBUG for more verbose output during development


