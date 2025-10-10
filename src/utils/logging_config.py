import logging
import os

def setup_logging():
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../ascendant_vision_ai_platform.log')
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured. Messages will be saved to ascendant_vision_ai_platform.log and shown in console.")
    logger.info(f"Log file location: {log_file_path}")