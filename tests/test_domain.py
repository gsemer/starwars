from __future__ import annotations

from app.domain.exceptions import DomainError, EntityNotFoundError, ExternalServiceError
from app.domain.import_result import ImportResult


def test_entity_not_found_error_message() -> None:
    exc = EntityNotFoundError("Character", "abc-123")
    assert "Character" in str(exc)
    assert "abc-123" in str(exc)
    assert exc.entity_name == "Character"
    assert exc.identifier == "abc-123"
    assert isinstance(exc, DomainError)


def test_external_service_error_message() -> None:
    exc = ExternalServiceError("SWAPI", "timeout")
    assert "SWAPI" in str(exc)
    assert "timeout" in str(exc)
    assert isinstance(exc, DomainError)


def test_import_result_defaults() -> None:
    result = ImportResult("films")
    assert result.resource == "films"
    assert result.imported == 0
    assert result.batches == 0


def test_import_result_to_dict() -> None:
    result = ImportResult("people")
    result.imported = 5
    result.batches = 2
    assert result.to_dict() == {"resource": "people", "imported": 5, "batches": 2}
