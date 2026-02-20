"""
LocalArtifactStore — filesystem-backed implementation of ArtifactStore.

Wraps the existing models/versions/ directory layout used by ModelManager.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LocalArtifactStore:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.versions_dir = self.base_dir / "versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def save(self, version: str, artifacts: Dict[str, Any]) -> str:
        version_dir = self.versions_dir / version
        version_dir.mkdir(parents=True, exist_ok=True)

        for name, data in artifacts.items():
            path = version_dir / name
            if isinstance(data, bytes):
                path.write_bytes(data)
            elif isinstance(data, dict):
                path.write_text(json.dumps(data, indent=2))
            else:
                path.write_text(str(data))

        logger.info(f"Saved artifacts for {version} to {version_dir}")
        return str(version_dir)

    def load(self, version: str) -> Dict[str, Any]:
        version_dir = self.versions_dir / version
        if not version_dir.exists():
            raise FileNotFoundError(f"No artifacts for version {version}")

        artifacts = {}
        for path in version_dir.iterdir():
            if path.is_file():
                artifacts[path.name] = path
        return artifacts

    def list_versions(self) -> List[str]:
        if not self.versions_dir.exists():
            return []
        return sorted(
            [d.name for d in self.versions_dir.iterdir() if d.is_dir()]
        )

    def delete(self, version: str) -> bool:
        version_dir = self.versions_dir / version
        if version_dir.exists():
            shutil.rmtree(version_dir)
            logger.info(f"Deleted artifacts for {version}")
            return True
        return False

    def exists(self, version: str) -> bool:
        return (self.versions_dir / version).exists()

    def get_metadata(self, version: str) -> Optional[Dict[str, Any]]:
        version_dir = self.versions_dir / version
        metadata_path = version_dir / "metadata.json"
        if metadata_path.exists():
            return json.loads(metadata_path.read_text())
        return None
