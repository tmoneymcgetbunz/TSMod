"""Double-click to start the TSMod Save Editor (needs the project's Python: .venv\Scripts\pythonw.exe)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from saveeditor.app import main
main()
