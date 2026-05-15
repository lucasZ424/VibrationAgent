# S1 — Document ingestion & parsing (prompt template)

You process one document at a time. For each page emit the block schema defined in
§十 of the design doc:

```
{
  "doc_id": "...", "page_no": N, "primary_engine": "paddleocr|tesseract",
  "fallback_used": bool, "ocr_confidence": float, "layout_quality": "low|medium|high",
  "raw_text": "...", "normalized_text": "...",
  "blocks": [{"block_id": "...", "text": "...", "bbox": [x1,y1,x2,y2]}],
  "needs_review": bool
}
```

Do **not** try to interpret content. Do **not** guess missing text. Flag the page for
human review instead.
