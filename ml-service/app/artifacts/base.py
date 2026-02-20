"""
ArtifactStore protocol — abstraction for model artifact storage.

Phase 1: LocalArtifactStore (filesystem).
Phase 3: S3ArtifactStore, PostgresArtifactStore, etc.
"""

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class ArtifactStore(Protocol):
    def save(self, version: str, artifacts: Dict[str, Any]) -> str:
        """Save model artifacts for a version. Returns the storage path/key."""
        ...

    def load(self, version: str) -> Dict[str, Any]:
        """Load model artifacts for a version."""
        ...

    def list_versions(self) -> list[str]:
        """List all stored model versions."""
        ...

    def delete(self, version: str) -> bool:
        """Delete artifacts for a version."""
        ...

    def exists(self, version: str) -> bool:
        """Check if artifacts exist for a version."""
        ...

    def get_metadata(self, version: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a stored version."""
        ...
