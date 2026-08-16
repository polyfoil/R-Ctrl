"""R-Ctrl shared core.

All entry points (widget, server, cloud CLI) build on these modules so that
recording, transcription, text cleanup and text injection behave identically
everywhere. Before this package existed the same logic lived in four copies
that had already drifted apart.
"""

__version__ = "1.0.0"
