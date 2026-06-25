from vibration_agent.ingestion.ocr import router
from vibration_agent.schemas import OcrPage, PageBlock


def _page(*, text: str, confidence: float | None, engine: str = "paddleocr") -> OcrPage:
    return OcrPage(
        doc_id="doc1",
        page_no=1,
        primary_engine=engine,
        fallback_used=False,
        ocr_confidence=confidence,
        layout_quality="ok" if text else "empty",
        raw_text=text,
        normalized_text=text,
        blocks=[PageBlock(block_id="p0001_b0001", text=text, confidence=confidence)] if text else [],
        needs_review=confidence is None or confidence < 0.6 or not text,
    )


def test_router_returns_paddle_when_confidence_is_sufficient(monkeypatch):
    calls = []

    monkeypatch.setattr(router.paddle_engine, "run", lambda *args, **kwargs: _page(text="rotor vibration", confidence=0.95))
    monkeypatch.setattr(router.tesseract_engine, "run", lambda *args, **kwargs: calls.append("fallback") or _page(text="fallback", confidence=0.8, engine="tesseract"))

    page = router.ocr_page("dummy.pdf", 1, doc_id="doc1", low_confidence_threshold=0.6)

    assert page.primary_engine == "paddleocr"
    assert page.fallback_used is False
    assert calls == []


def test_router_uses_more_informative_fallback_on_low_confidence(monkeypatch):
    monkeypatch.setattr(router.paddle_engine, "run", lambda *args, **kwargs: _page(text="rotor", confidence=0.4))
    monkeypatch.setattr(
        router.tesseract_engine,
        "run",
        lambda *args, **kwargs: _page(text="rotor vibration bearing diagnostics", confidence=0.8, engine="tesseract"),
    )

    page = router.ocr_page("dummy.pdf", 1, doc_id="doc1", low_confidence_threshold=0.6)

    assert page.primary_engine == "tesseract"
    assert page.fallback_used is True
    assert page.normalized_text == "rotor vibration bearing diagnostics"


def test_router_marks_primary_for_review_when_fallback_is_not_better(monkeypatch):
    monkeypatch.setattr(router.paddle_engine, "run", lambda *args, **kwargs: _page(text="rotor vibration bearing", confidence=0.4))
    monkeypatch.setattr(router.tesseract_engine, "run", lambda *args, **kwargs: _page(text="rotor", confidence=0.8, engine="tesseract"))

    page = router.ocr_page("dummy.pdf", 1, doc_id="doc1", low_confidence_threshold=0.6)

    assert page.primary_engine == "paddleocr"
    assert page.fallback_used is True
    assert page.needs_review is True


def test_router_preserves_primary_when_fallback_crashes(monkeypatch):
    # WHY: an optional recovery engine must not discard usable Paddle text or abort a long OCR batch.
    monkeypatch.setattr(router.paddle_engine, "run", lambda *args, **kwargs: _page(text="rotor vibration", confidence=0.4))
    monkeypatch.setattr(
        router.tesseract_engine,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("render failed")),
    )

    page = router.ocr_page("dummy.pdf", 1, doc_id="doc1", low_confidence_threshold=0.6)

    assert page.primary_engine == "paddleocr"
    assert page.normalized_text == "rotor vibration"
    assert page.fallback_used is True
    assert page.needs_review is True


def test_image_router_uses_tesseract_for_empty_paddle_result(monkeypatch):
    # WHY: retained figure regions need the same recovery policy as full scanned pages.
    monkeypatch.setattr(router.paddle_engine, "run_image", lambda *args, **kwargs: _page(text="", confidence=None))
    monkeypatch.setattr(
        router.tesseract_engine,
        "run_image",
        lambda *args, **kwargs: _page(text="axis speed amplitude", confidence=None, engine="tesseract"),
    )

    page = router.ocr_image("figure.png", doc_id="doc1", page_no=2)

    assert page.primary_engine == "tesseract"
    assert page.fallback_used is True
    assert page.normalized_text == "axis speed amplitude"
