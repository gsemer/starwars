from __future__ import annotations

from app.domain.pagination import PageResult, PaginationParams


def test_default_pagination() -> None:
    params = PaginationParams()
    assert params.page == 1
    assert params.page_size == 20


def test_page_below_one_is_clamped() -> None:
    assert PaginationParams(page=0, page_size=10).page == 1


def test_negative_page_is_clamped() -> None:
    assert PaginationParams(page=-5, page_size=10).page == 1


def test_page_size_below_one_is_clamped() -> None:
    assert PaginationParams(page=1, page_size=0).page_size == 1


def test_page_size_above_max_is_clamped() -> None:
    assert PaginationParams(page=1, page_size=500).page_size == 100


def test_valid_values_pass_through() -> None:
    params = PaginationParams(page=3, page_size=50)
    assert params.page == 3
    assert params.page_size == 50


def test_page_result_total_pages_rounds_up() -> None:
    result = PageResult(items=[], total=21, page=1, page_size=20)
    assert result.total_pages == 2


def test_page_result_total_pages_exact_division() -> None:
    result = PageResult(items=[], total=40, page=1, page_size=20)
    assert result.total_pages == 2


def test_page_result_total_pages_zero_total() -> None:
    result = PageResult(items=[], total=0, page=1, page_size=20)
    assert result.total_pages == 0


def test_page_result_total_pages_zero_page_size_is_safe() -> None:
    result = PageResult(items=[], total=10, page=1, page_size=0)
    assert result.total_pages == 0
