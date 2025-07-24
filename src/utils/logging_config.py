import logging
import os

def setup_logging():
    """
    Configures the application's logging system.
    Logs messages to both a file (app_log.log) and the console.
    Sets the default logging level to INFO.
    """
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../app_log.log')
    # Ensure the directory for the log file exists
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Basic configuration for the root logger
    logging.basicConfig(
        level=logging.INFO, # Set the default logging level (INFO, DEBUG, WARNING, ERROR, CRITICAL)
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler: logs all messages to a file
            logging.FileHandler(log_file_path, encoding='utf-8'),
            # Stream handler: logs messages to the console (stdout)
            logging.StreamHandler()
        ]
    )

    # Suppress overly verbose logs from external libraries if needed
    # Example: PIL (Pillow) can be chatty with INFO/DEBUG messages
    logging.getLogger('PIL').setLevel(logging.WARNING)
    # urllib3 (used by requests, http.client) can also be noisy
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    # OpenAI library might also have its own logging
    logging.getLogger('openai').setLevel(logging.WARNING)

    # Get a logger for this specific module to confirm setup
    logger = logging.getLogger(__name__)
    logger.info("Logging configured. Messages will be saved to app_log.log and shown in console.")
    logger.info(f"Log file location: {log_file_path}")


