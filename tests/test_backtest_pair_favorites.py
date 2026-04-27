from app.core.parsing.json_parser import write_json_file_atomic
from app.web.api.routes.backtest import _load_favorites, _normalize_pairs


def test_normalize_pairs_preserves_order_and_removes_duplicates() -> None:
    assert _normalize_pairs([" ADA/USDT ", "BNB/USDT", "ADA/USDT", "", "BNB/USDT"]) == [
        "ADA/USDT",
        "BNB/USDT",
    ]


def test_load_favorites_normalizes_persisted_duplicates(tmp_path) -> None:
    write_json_file_atomic(
        tmp_path / "favorites.json",
        {"favorites": ["ADA/USDT", " ADA/USDT ", "BNB/USDT", ""]},
    )

    assert _load_favorites(tmp_path) == ["ADA/USDT", "BNB/USDT"]
