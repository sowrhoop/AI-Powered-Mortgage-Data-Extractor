import sys
import os
import ctypes
import logging

logger = logging.getLogger(__name__)

def get_base_path() -> str:
    """
    Determines the base path for the application.
    Works correctly whether the script is run directly or as a PyInstaller executable.
    :return: The absolute path to the application's base directory.
    """
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (e.g., created by PyInstaller)
        # sys.executable is the path to the executable.
        base_path = os.path.dirname(sys.executable)
        logger.debug(f"Running as frozen executable. Base path: {base_path}")
    else:
        # If the application is run as a script
        # __file__ is the path to the current script.
        base_path = os.path.dirname(os.path.abspath(__file__))
        # For a nested structure like src/utils, we want the root 'document_analyzer_app'
        # Go up two levels from src/utils to document_analyzer_app
        base_path = os.path.abspath(os.path.join(base_path, os.pardir, os.pardir))
        logger.debug(f"Running as script. Base path: {base_path}")
    return base_path

def get_dpi_scale_factor() -> float:
    """
    Attempts to retrieve the system's DPI scaling factor, primarily for Windows.
    This is crucial for accurate screen capture coordinates on high-resolution displays.
    :return: The DPI scale factor (e.g., 1.0 for 100%, 1.5 for 150%). Defaults to 1.0 if not found.
    """
    try:
        # For Windows, use GetScaleFactorForDevice API
        # 0 represents the primary display device
        return ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0
    except (AttributeError, OSError):
        # Fallback for non-Windows operating systems or if the API is not available
        logger.warning("Could not retrieve system DPI scale factor. Defaulting to 1.0. "
                       "Screen capture accuracy might be affected on high-DPI displays.")
        return 1.0
    except Exception as e:
        logger.error(f"An unexpected error occurred while getting DPI scale factor: {e}", exc_info=True)
        return 1.0

def is_admin() -> bool:
    """
    Checks if the current script is running with administrator privileges on Windows.
    :return: True if running as admin, False otherwise.
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        logger.error(f"Could not determine admin status: {e}", exc_info=True)
        return False

def run_as_admin():
    """
    Attempts to restart the script with administrator privileges on Windows.
    This function will cause the current process to exit and a new one to launch.
    :return: True if the elevation attempt was successful (and current process should exit),
             False if elevation failed or not on Windows.
    """
    if is_admin():
        logger.info("Already running with administrator privileges.")
        return True
    else:
        if sys.platform == "win32":
            try:
                # Re-run the program with admin rights
                # ShellExecuteW is a Windows API call to execute a program
                # 'runas' verb requests elevation
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
                logger.info("Attempting to re-launch script with administrator privileges.")
                return True # Indicate that the current process should exit
            except Exception as e:
                logger.error(f"Failed to elevate privileges: {e}", exc_info=True)
                return False
        else:
            logger.warning("Admin elevation is only supported on Windows.")
            return False