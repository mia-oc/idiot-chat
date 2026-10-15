"""Single-shot capture, called only during an explicitly activated session."""
import io
import sys


class CaptureError(RuntimeError):
    pass


PERMISSION_GUIDE = (
    'Screen capture failed. On macOS, open System Settings > Privacy & Security > '
    'Screen & System Audio Recording (Screen Recording on older versions). '
    'Allow the terminal or Python application used to launch Idiot Chat, then quit '
    'and reopen it. Fix permissions and restart Watch and Chat.'
)


def capture_screen():
    try:
        if sys.platform == 'darwin':
            import ctypes
            import ctypes.util
            library = ctypes.util.find_library('CoreGraphics')
            if library:
                graphics = ctypes.CDLL(library)
                if hasattr(graphics, 'CGPreflightScreenCaptureAccess'):
                    graphics.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
                    graphics.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
                    if not graphics.CGPreflightScreenCaptureAccess():
                        graphics.CGRequestScreenCaptureAccess()
                        raise CaptureError(PERMISSION_GUIDE)
        from PIL import Image, ImageGrab
        picture = ImageGrab.grab()
        if picture.width == 0 or picture.height == 0:
            raise CaptureError(PERMISSION_GUIDE)
        picture.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        picture.convert('RGB').save(output, format='PNG')
        return output.getvalue()
    except CaptureError:
        raise
    except Exception:
        # OS exception strings can contain paths; show actionable fixed guidance.
        raise CaptureError(PERMISSION_GUIDE) from None
