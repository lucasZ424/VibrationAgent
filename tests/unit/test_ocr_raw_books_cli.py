from scripts.ocr_raw_books_with_paddle import parse_args


def test_resumable_ocr_cli_enables_fallback_by_default():
    # WHY: bulk OCR must not silently bypass the configured Paddle-to-Tesseract recovery lane.
    assert parse_args([]).use_fallback is True


def test_resumable_ocr_cli_allows_explicit_fallback_disable():
    # WHY: operators need a narrow troubleshooting escape hatch without changing production defaults.
    assert parse_args(["--no-fallback"]).use_fallback is False
