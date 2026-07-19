from __future__ import annotations

import unittest

from app.domain.pagination import PageResult, PaginationParams


class PaginationParamsTests(unittest.TestCase):
    def test_default_pagination(self) -> None:
        params = PaginationParams()
        self.assertEqual(params.page, 1)
        self.assertEqual(params.page_size, 20)

    def test_page_below_one_is_clamped(self) -> None:
        self.assertEqual(PaginationParams(page=0, page_size=10).page, 1)

    def test_negative_page_is_clamped(self) -> None:
        self.assertEqual(PaginationParams(page=-5, page_size=10).page, 1)

    def test_page_size_below_one_is_clamped(self) -> None:
        self.assertEqual(PaginationParams(page=1, page_size=0).page_size, 1)

    def test_page_size_above_max_is_clamped(self) -> None:
        self.assertEqual(PaginationParams(page=1, page_size=500).page_size, 100)

    def test_valid_values_pass_through(self) -> None:
        params = PaginationParams(page=3, page_size=50)
        self.assertEqual(params.page, 3)
        self.assertEqual(params.page_size, 50)


class PageResultTests(unittest.TestCase):
    def test_total_pages_rounds_up(self) -> None:
        self.assertEqual(PageResult(items=[], total=21, page=1, page_size=20).total_pages, 2)

    def test_total_pages_exact_division(self) -> None:
        self.assertEqual(PageResult(items=[], total=40, page=1, page_size=20).total_pages, 2)

    def test_total_pages_zero_total(self) -> None:
        self.assertEqual(PageResult(items=[], total=0, page=1, page_size=20).total_pages, 0)

    def test_total_pages_zero_page_size_is_safe(self) -> None:
        self.assertEqual(PageResult(items=[], total=10, page=1, page_size=0).total_pages, 0)


if __name__ == "__main__":
    unittest.main()