"""
Media downloader with deduplication support.

Provides:
- Content-hash based deduplication (dedup.py)
- Media download with proper naming and storage (downloader.py)
"""

from .dedup import DedupIndex, DedupResult
from .downloader import MediaDownloader, DownloadResult, DownloadStats

__all__ = [
    "DedupIndex",
    "DedupResult",
    "MediaDownloader",
    "DownloadResult",
    "DownloadStats",
]
