"""Used by TSModSaveEditor.bat: prints this Python's path if it can run the editor (3.11+ with Tk), else exits 1."""
import sys
try:
    import tkinter  # noqa: F401  (python.org installs include it)
except Exception:
    sys.exit(1)
if sys.version_info < (3, 11):
    sys.exit(1)
print(sys.executable)
