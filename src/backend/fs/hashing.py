"""
Content hashing utilities for media deduplication.

Uses SHA-256 for content hashing. The first 6 characters (hash6) are used
in filenames for traceability, while the full hash is used for deduplication.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO


# Hash algorithm to use
HASH_ALGORITHM = "sha256"

# Size of hash prefix used in filenames
HASH6_LENGTH = 6

# Buffer size for streaming hash computation
BUFFER_SIZE = 65536  # 64 KB


def compute_file_hash(file_path: Path | str) -> str:
    """
    Compute the SHA-256 hash of a file's contents.

    Args:
        file_path: Path to the file.

    Returns:
        Lowercase hexadecimal hash string.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        IOError: If the file cannot be read.
    """
    path = Path(file_path)
    hasher = hashlib.new(HASH_ALGORITHM)

    with open(path, 'rb') as f:
        _update_hash_from_stream(hasher, f)

    return hasher.hexdigest()


def compute_bytes_hash(data: bytes) -> str:
    """
    Compute the SHA-256 hash of bytes.

    Args:
        data: The bytes to hash.

    Returns:
        Lowercase hexadecimal hash string.
    """
    return hashlib.new(HASH_ALGORITHM, data).hexdigest()


def compute_stream_hash(stream: BinaryIO) -> str:
    """
    Compute the SHA-256 hash from a binary stream.

    Args:
        stream: A binary stream (file-like object).

    Returns:
        Lowercase hexadecimal hash string.
    """
    hasher = hashlib.new(HASH_ALGORITHM)
    _update_hash_from_stream(hasher, stream)
    return hasher.hexdigest()


def _update_hash_from_stream(hasher, stream: BinaryIO) -> None:
    """Update a hash object from a stream in chunks."""
    while True:
        chunk = stream.read(BUFFER_SIZE)
        if not chunk:
            break
        hasher.update(chunk)


def compute_hash6(full_hash: str) -> str:
    """
    Extract the first 6 characters of a hash for filename use.

    Args:
        full_hash: The full hexadecimal hash string.

    Returns:
        First 6 characters of the hash, lowercase.

    Raises:
        ValueError: If the hash is shorter than 6 characters.
    """
    if len(full_hash) < HASH6_LENGTH:
        raise ValueError(
            f"Hash must be at least {HASH6_LENGTH} characters, got {len(full_hash)}"
        )
    return full_hash[:HASH6_LENGTH].lower()


def compute_file_hash6(file_path: Path | str) -> str:
    """
    Compute the hash6 (first 6 characters of SHA-256) for a file.

    Args:
        file_path: Path to the file.

    Returns:
        First 6 characters of the file's hash.
    """
    full_hash = compute_file_hash(file_path)
    return compute_hash6(full_hash)


class StreamHasher:
    """
    A write-through hasher that computes hash while writing data.

    Usage:
        hasher = StreamHasher()
        with open('output.bin', 'wb') as f:
            for chunk in download_stream:
                f.write(chunk)
                hasher.update(chunk)
        full_hash = hasher.hexdigest()
        hash6 = hasher.hash6()
    """

    def __init__(self):
        """Initialize a new stream hasher."""
        self._hasher = hashlib.new(HASH_ALGORITHM)
        self._size = 0

    def update(self, data: bytes) -> None:
        """Update the hash with more data."""
        self._hasher.update(data)
        self._size += len(data)

    def hexdigest(self) -> str:
        """Get the hexadecimal hash string."""
        return self._hasher.hexdigest()

    def hash6(self) -> str:
        """Get the first 6 characters of the hash."""
        return compute_hash6(self.hexdigest())

    @property
    def size(self) -> int:
        """Get the total size of data hashed so far."""
        return self._size

    def copy(self) -> "StreamHasher":
        """Create a copy of this hasher with current state."""
        new_hasher = StreamHasher()
        new_hasher._hasher = self._hasher.copy()
        new_hasher._size = self._size
        return new_hasher
