from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ImportResult:
    """Summarizes the outcome of importing one resource type from SWAPI."""

    resource: str
    imported: int = field(default=0)
    batches: int = field(default=0)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes this result to a plain dict, e.g. for an API response."""
        return {"resource": self.resource, "imported": self.imported, "batches": self.batches}

    @classmethod
    def from_dict(cls, data: dict) -> "ImportResult":
        return cls(
            resource=data["resource"],
            imported=data["imported"],
            batches=data["batches"],
        )
