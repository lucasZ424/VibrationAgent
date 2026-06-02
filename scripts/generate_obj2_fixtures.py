"""Regenerate Phase-2 Obj2 bilingual and cross-page fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vibration_agent.ingestion.chunking import chunk_pages, write_jsonl  # noqa: E402
from vibration_agent.ingestion.pymupdf_parser import parse_native_pdf  # noqa: E402
from vibration_agent.retrieval.hybrid import search  # noqa: E402


TITLE = "\u0031 \u8f6c\u5b50\u963b\u5c3c\u4e0e\u4e34\u754c\u8f6c\u901f"
P1_BODY_1 = (
    "\u963b\u5c3c\u6bd4 \u03b6 \u8868\u793a\u7cfb\u7edf\u8017\u6563\u80fd\u91cf\u7684"
    "\u80fd\u529b\u3002\u963b\u5c3c\u6bd4\u589e\u52a0\u65f6\uff0c\u81ea\u7531\u632f\u52a8"
    "\u8870\u51cf\u66f4\u5feb\u3002"
)
P1_BODY_2 = (
    "\u8f6c\u5b50\u63a5\u8fd1\u4e34\u754c\u8f6c\u901f\u65f6\uff0c\u54cd\u5e94"
    "\u5e45\u503c\u4f1a\u653e\u5927\uff0c\u76f8\u4f4d\u4e5f\u4f1a\u5feb\u901f"
    "\u53d8\u5316\u3002"
)
P1_BODY_3 = (
    "\u5de5\u7a0b\u4e0a\u4f1a\u5173\u6ce8\u4e34\u754c\u8f6c\u901f\u9644\u8fd1"
    "\u7684\u632f\u52a8\u5e45\u503c\uff0c\u56e0\u4e3a\u8be5\u533a\u95f4\u5bf9"
    "\u963b\u5c3c\u53d8\u5316\u5f88\u654f\u611f\u3002"
)
P2_BODY_1 = (
    "\u589e\u52a0\u963b\u5c3c\u901a\u5e38\u964d\u4f4e\u5171\u632f\u5cf0\u503c"
    "\u54cd\u5e94\uff0c\u5e76\u4f7f\u901a\u8fc7\u5171\u632f\u533a\u66f4\u5e73\u7a33\u3002"
)
P2_BODY_2 = (
    "\u72b6\u6001\u76d1\u6d4b\u5e94\u540c\u65f6\u89c2\u5bdf\u632f\u5e45\u3001"
    "\u76f8\u4f4d\u548c\u8f74\u5fc3\u8f68\u8ff9\uff0c\u7528\u6765\u5224\u65ad"
    "\u8f6c\u5b50\u632f\u52a8\u98ce\u9669\u3002"
)
P2_BODY_3 = (
    "\u5982\u679c\u963b\u5c3c\u4e0d\u8db3\uff0c\u673a\u7ec4\u5728\u5347\u901f"
    "\u6216\u964d\u901f\u901a\u8fc7\u5171\u632f\u533a\u65f6\u66f4\u5bb9\u6613"
    "\u51fa\u73b0\u8fc7\u5927\u632f\u52a8\u3002"
)
DOC_TITLE = "\u8f6c\u5b50\u963b\u5c3c\u4e2d\u6587\u6837\u4f8b"
QUERY = "\u963b\u5c3c\u6bd4 \u4e34\u754c\u8f6c\u901f \u8f6c\u5b50\u632f\u52a8"


def _write_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for blocks in (
        ((TITLE, 14, 72, 72), (P1_BODY_1, 11, 72, 106), (P1_BODY_2, 11, 72, 124), (P1_BODY_3, 11, 72, 142)),
        ((P2_BODY_1, 11, 72, 72), (P2_BODY_2, 11, 72, 90), (P2_BODY_3, 11, 72, 108)),
    ):
        page = doc.new_page()
        for text, size, x, y in blocks:
            page.insert_text((x, y), text, fontname="china-s", fontsize=size)
    doc.save(path)
    doc.close()


def main() -> int:
    fixtures = ROOT / "tests" / "fixtures"
    raw_pdf = fixtures / "raw" / "small_vibration_zh.pdf"
    _write_pdf(raw_pdf)

    pages = parse_native_pdf(raw_pdf, doc_id="fixture_rotor_zh_doc", extract_image_assets=False)
    page_rows = [{"schema_version": "0.1", **page.model_dump(mode="json")} for page in pages]
    write_jsonl(fixtures / "ocr" / "sample_zh_pages.jsonl", page_rows)

    chunks = chunk_pages(
        pages,
        doc_id="fixture_rotor_zh_doc",
        title=DOC_TITLE,
        source_path="tests/fixtures/raw/small_vibration_zh.pdf",
        source_type="book",
        target_tokens=600,
        overlap_tokens=60,
    )
    write_jsonl(fixtures / "chunks" / "sample_zh_chunks.jsonl", chunks)

    retrieval = search(QUERY, chunks=chunks, top_k=1)
    retrieval_payload = {key: retrieval[key] for key in ("normalized_query", "intent", "status", "warnings", "hits")}
    (fixtures / "retrieval" / "sample_zh_retrieval.json").write_text(
        json.dumps(retrieval_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {raw_pdf}")
    print(f"chunks={len(chunks)} pages={chunks[0]['pages'] if chunks else []}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
