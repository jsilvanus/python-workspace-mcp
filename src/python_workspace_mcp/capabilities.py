from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceCapabilities:
    """Explicit capabilities for a workspace. Arbitrary outbound network is never implied."""

    package_install: bool = False
    package_index: str = "pypi"
    outbound_network: bool = False
    file_upload: bool = True
    file_download: bool = True

    def as_dict(self) -> dict:
        return {
            "package_install": self.package_install,
            "package_index": self.package_index,
            "outbound_network": self.outbound_network,
            "file_upload": self.file_upload,
            "file_download": self.file_download,
        }
