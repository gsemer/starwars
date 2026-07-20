"""Domain-level exceptions.

Framework-agnostic; the API layer translates these into HTTP responses.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain exceptions."""


class EntityNotFoundError(DomainError):
    """Raised when a requested entity cannot be found."""

    def __init__(self, entity_name: str, identifier: str) -> None:
        """Builds the error with a message identifying the missing entity.

        Args:
            entity_name: Human-readable entity type, e.g. "Character".
            identifier: The identifier that was looked up and not found.
        """
        self.entity_name = entity_name
        self.identifier = identifier
        super().__init__(f"{entity_name} with identifier '{identifier}' was not found")


class ExternalServiceError(DomainError):
    """Raised when an external service (e.g. SWAPI) fails unrecoverably."""

    def __init__(self, service_name: str, message: str) -> None:
        """Builds the error with a message identifying the failing service.

        Args:
            service_name: Name of the external service, e.g. "SWAPI".
            message: Details about the failure (e.g. the last error seen).
        """
        self.service_name = service_name
        super().__init__(f"{service_name} error: {message}")


class ImportInProgressError(DomainError):
    """Raised when an import is running elsewhere but did not finish within
    the caller's wait budget. Distinct from `ExternalServiceError`: nothing
    failed, the work is simply still in progress — the client should retry.
    """
    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"An import for '{resource}' is in progress; retry shortly")

