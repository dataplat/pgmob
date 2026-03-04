"""Metadata provider module for pgmob.

Provides the MetadataProvider abstract base class and concrete implementations
for retrieving PostgreSQL object metadata.
"""

from .base import MetadataProvider
from .sql import SQLMetadataProvider

__all__ = ["MetadataProvider", "SQLMetadataProvider"]
