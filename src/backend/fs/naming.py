"""
Media file naming conventions.

Filename format: <tweetId>_<YYYY-MM-DD>_<hash6>.<ext>

- tweetId: The ID of the tweet containing the media
- YYYY-MM-DD: The date from the tweet's created_at timestamp
- hash6: First 6 characters of the content hash (for dedup traceability)
- ext: File extension (e.g., jpg, png, mp4)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ParsedFilename:
    """Parsed components of a media filename."""
    tweet_id: str
    date: str          # YYYY-MM-DD
    hash6: str         # 6-character hash prefix
    extension: str     # Without dot


# Pattern to match our filename format: <tweetId>_<YYYY-MM-DD>_<hash6>.<ext>
FILENAME_PATTERN = re.compile(
    r'^(\d+)_(\d{4}-\d{2}-\d{2})_([a-f0-9]{6})\.(\w+)$',
    re.IGNORECASE
)


def generate_media_filename(
    tweet_id: str,
    created_at: datetime,
    hash6: str,
    extension: str,
) -> str:
    """
    Generate a media filename following the naming convention.

    Args:
        tweet_id: The ID of the tweet.
        created_at: The tweet's creation timestamp.
        hash6: First 6 characters of the content hash.
        extension: File extension (with or without leading dot).

    Returns:
        Formatted filename: <tweetId>_<YYYY-MM-DD>_<hash6>.<ext>

    Raises:
        ValueError: If hash6 is not exactly 6 characters or contains invalid chars.
    """
    # Validate hash6
    if len(hash6) != 6:
        raise ValueError(f"hash6 must be exactly 6 characters, got {len(hash6)}")
    if not re.match(r'^[a-f0-9]{6}$', hash6.lower()):
        raise ValueError(f"hash6 must be hexadecimal, got {hash6!r}")

    # Format date as YYYY-MM-DD
    date_str = created_at.strftime("%Y-%m-%d")

    # Clean extension (remove leading dot if present)
    ext = extension.lstrip('.')

    return f"{tweet_id}_{date_str}_{hash6.lower()}.{ext}"


def parse_media_filename(filename: str) -> Optional[ParsedFilename]:
    """
    Parse a media filename to extract its components.

    Args:
        filename: The filename to parse (can include path).

    Returns:
        ParsedFilename if the filename matches the convention, None otherwise.
    """
    # Extract just the filename if a path was provided
    from pathlib import Path
    name = Path(filename).name

    match = FILENAME_PATTERN.match(name)
    if not match:
        return None

    return ParsedFilename(
        tweet_id=match.group(1),
        date=match.group(2),
        hash6=match.group(3).lower(),
        extension=match.group(4).lower(),
    )


def extract_tweet_id(filename: str) -> Optional[str]:
    """
    Extract just the tweet ID from a filename.

    Args:
        filename: The filename to parse.

    Returns:
        The tweet ID if found, None otherwise.
    """
    parsed = parse_media_filename(filename)
    return parsed.tweet_id if parsed else None


def get_extension_for_mime(mime_type: str) -> str:
    """
    Get the file extension for a MIME type.

    Args:
        mime_type: The MIME type (e.g., 'image/jpeg', 'video/mp4').

    Returns:
        File extension without dot (e.g., 'jpg', 'mp4').
    """
    # Common mappings
    mime_to_ext = {
        'image/jpeg': 'jpg',
        'image/jpg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp',
        'video/mp4': 'mp4',
        'video/webm': 'webm',
        'video/quicktime': 'mov',
    }

    mime_lower = mime_type.lower().split(';')[0].strip()
    return mime_to_ext.get(mime_lower, mime_lower.split('/')[-1])


def get_extension_from_url(url: str) -> str:
    """
    Extract file extension from a URL.

    Args:
        url: The URL to parse.

    Returns:
        File extension without dot, or 'bin' if not determinable.
    """
    from urllib.parse import urlparse
    path = urlparse(url).path

    # Get the last part of the path
    if '.' in path:
        ext = path.rsplit('.', 1)[-1].lower()
        # Clean up query params if they snuck in
        ext = ext.split('?')[0].split('&')[0]
        # Validate it looks like an extension
        if 1 <= len(ext) <= 10 and ext.isalnum():
            return ext

    return 'bin'
