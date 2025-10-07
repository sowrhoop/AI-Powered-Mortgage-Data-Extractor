import sys
import os
import ctypes
from ctypes import wintypes
import logging

logger = logging.getLogger(__name__)

def get_base_path() -> str:
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
        logger.debug(f"Running as frozen executable. Base path: {base_path}")
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.abspath(os.path.join(base_path, os.pardir, os.pardir))
        logger.debug(f"Running as script. Base path: {base_path}")
    return base_path

def get_dpi_scale_factor() -> float:
    try:
        return ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0
    except (AttributeError, OSError):
        logger.warning("Could not retrieve system DPI scale factor. Defaulting to 1.0. "
                       "Screen capture accuracy might be affected on high-DPI displays.")
        return 1.0
    except Exception as e:
        logger.error(f"An unexpected error occurred while getting DPI scale factor: {e}", exc_info=True)
        return 1.0

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        logger.error(f"Could not determine admin status: {e}", exc_info=True)
        return False

def run_as_admin():
    if is_admin():
        logger.info("Already running with administrator privileges.")
        return True
    else:
        if sys.platform == "win32":
            try:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
                logger.info("Attempting to re-launch script with administrator privileges.")
                return True
            except Exception as e:
                logger.error(f"Failed to elevate privileges: {e}", exc_info=True)
                return False
        else:
            logger.warning("Admin elevation is only supported on Windows.")
            return False

def get_work_area() -> tuple:
    """Return the desktop work area (left, top, right, bottom) excluding the taskbar.
    Falls back to full screen metrics if SPI call is unavailable.
    """
    try:
        SPI_GETWORKAREA = 0x0030
        rect = wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        if ok:
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception as e:
        logger.debug(f"SPI_GETWORKAREA failed: {e}")
    try:
        # Fallback to full screen size
        SM_CXSCREEN = 0
        SM_CYSCREEN = 1
        width = ctypes.windll.user32.GetSystemMetrics(SM_CXSCREEN)
        height = ctypes.windll.user32.GetSystemMetrics(SM_CYSCREEN)
        return (0, 0, width, height)
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return (0, 0, 1920, 1080)