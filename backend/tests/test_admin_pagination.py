import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.routers.admin import build_pagination, with_page_urls  # noqa: E402


def test_build_pagination_clamps_page_and_calculates_window():
    pagination = build_pagination(total=45, page=99, per_page=20)

    assert pagination["page"] == 3
    assert pagination["pages"] == 3
    assert pagination["start"] == 41
    assert pagination["end"] == 45
    assert pagination["has_prev"] is True
    assert pagination["has_next"] is False


def test_build_pagination_handles_empty_result_set():
    pagination = build_pagination(total=0, page=-5, per_page=20)

    assert pagination["page"] == 1
    assert pagination["pages"] == 1
    assert pagination["start"] == 0
    assert pagination["end"] == 0
    assert pagination["has_prev"] is False
    assert pagination["has_next"] is False


def test_with_page_urls_preserves_filters_and_encodes_query_values():
    pagination = build_pagination(total=30, page=1, per_page=20)
    pagination = with_page_urls(
        pagination,
        "/admin/afiliados",
        estado="SP",
        cidade="São Paulo",
        profissao="entregador",
        vazio="",
    )

    assert pagination["next_url"] == (
        "/admin/afiliados?estado=SP&cidade=S%C3%A3o+Paulo&profissao=entregador&page=2"
    )
    assert "vazio" not in pagination["next_url"]
