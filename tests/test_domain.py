from __future__ import annotations

import unittest

from app.domain.exceptions import DomainError, EntityNotFoundError, ExternalServiceError
from app.domain.import_result import ImportResult


class ExceptionTests(unittest.TestCase):
    def test_entity_not_found_error_message(self) -> None:
        exc = EntityNotFoundError("Character", "abc-123")
        self.assertIn("Character", str(exc))
        self.assertIn("abc-123", str(exc))
        self.assertEqual(exc.entity_name, "Character")
        self.assertEqual(exc.identifier, "abc-123")
        self.assertIsInstance(exc, DomainError)

    def test_external_service_error_message(self) -> None:
        exc = ExternalServiceError("SWAPI", "timeout")
        self.assertIn("SWAPI", str(exc))
        self.assertIn("timeout", str(exc))
        self.assertIsInstance(exc, DomainError)


class ImportResultTests(unittest.TestCase):
    def test_defaults(self) -> None:
        result = ImportResult("films")
        self.assertEqual(result.resource, "films")
        self.assertEqual(result.imported, 0)
        self.assertEqual(result.batches, 0)

    def test_to_dict(self) -> None:
        result = ImportResult("people")
        result.imported = 5
        result.batches = 2
        self.assertEqual(result.to_dict(), {"resource": "people", "imported": 5, "batches": 2})

    def test_from_dict_round_trip(self) -> None:
        data = {"resource": "starships", "imported": 36, "batches": 1}
        result = ImportResult.from_dict(data)
        self.assertEqual(result.resource, "starships")
        self.assertEqual(result.imported, 36)
        self.assertEqual(result.batches, 1)
        self.assertEqual(result.to_dict(), data)


if __name__ == "__main__":
    unittest.main()