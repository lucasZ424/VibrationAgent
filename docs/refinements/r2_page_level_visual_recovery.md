# R2 Page-Level Visual Recovery and Hybrid OCR

Date: 2026-06-25
Status: STEPS 0-6 COMPLETE; STEP 7 CLEAN RE-INGESTION PENDING
Scope: native PDF page parsing, image-fragment recovery, mixed scanned-page OCR

## 1. Problem Statement

The current native PDF parser treats each PyMuPDF image block as an independent
asset. A real paper exposed 334,422 image blocks across 147 pages. Most blocks
were sub-point drawing fragments, and exporting each block created more than
120,000 tiny PNG files before the run was stopped.

The emergency guard now rejects image blocks whose width or height is below
4 PDF points and limits retained image assets per page. This prevents file
explosion, but it is not a complete extraction strategy.

Inspection of representative pages 25, 77, and 78 proved that tens of thousands
of tiny blocks can collectively form valid engineering figures:

- spectra and order plots;
- time-frequency surfaces;
- vibration displacement/velocity/acceleration diagrams;
- multi-panel research figures.

Therefore, a small block cannot be classified as worthless solely from its own
bbox. Classification must happen at page and cluster level.

## 2. Design Goals

1. Preserve native text whenever a usable text layer exists.
2. Detect occasional scanned pages inside otherwise native PDFs.
3. Recover valid figures represented by dense clusters of tiny blocks.
4. Discard decorative fragments without creating local files or database rows.
5. Keep uncertain fragments auditable without admitting them into retrieval.
6. Prevent pathological PDFs from causing unbounded CPU, memory, file, or JSON
   growth.
7. Keep OCR local-first: PaddleOCR primary, Tesseract conditional fallback.
8. Do not introduce VLM as a dependency in the first implementation.

## 3. Proposed Page Pipeline

```text
parse page
|
+-- extract text blocks
+-- extract image blocks
|
+-- calculate page features
|   +-- native text character count
|   +-- image block count
|   +-- tiny image block count and ratio
|   +-- union coverage of image regions
|   +-- tiny-block spatial density and clusters
|   +-- cluster position relative to the body region
|   +-- repeated header/footer signatures
|
+-- classify page FIRST
|   |
|   +-- suspected occasional scanned page
|   |   +-- render full page once
|   |   +-- PaddleOCR
|   |   +-- Tesseract fallback when required
|   |   +-- OCR text becomes page body text
|   |   +-- SKIP tiny-block cluster recovery for this page
|   |
|   +-- native or mixed page
|       +-- cluster tiny blocks
|       +-- render accepted cluster bboxes from the original page
|       +-- retain figure/table assets
|       +-- optionally OCR a bounded subset for additive metadata
|
+-- isolated decorative fragment
|   +-- discard or record as deferred diagnostic metadata
|
+-- semantic chunking
```

The original tiny blocks are never exported individually.

The scanned-page branch has precedence. A page cannot receive both full-page
OCR recovery and tiny-block cluster recovery in the same pass. This prevents a
scanned figure page from producing duplicate body text and duplicate assets.

## 4. Page Features

Introduce a deterministic page analysis result containing:

- `native_text_chars`
- `image_block_count`
- `tiny_image_block_count`
- `tiny_image_block_ratio`
- `valid_image_block_count`
- `image_union_coverage_ratio`
- `cluster_count`
- cluster bbox, block count, density, area ratio, and body-region overlap
- `header_footer_repeat_hits`
- `suspected_scanned_page`
- `suspected_fragmented_figure`

Coverage must use rectangle union or raster occupancy. Summing bbox areas is
invalid because dense fragments overlap heavily.

### 4.1 Body-region derivation

Body-region derivation is deterministic:

1. Define a page-safe region:
   - horizontal: 5% to 95% of page width;
   - vertical: 8% to 92% of page height.
2. If the page has at least three non-empty text blocks and at least 100 native
   text characters:
   - exclude text blocks wholly inside the top/bottom 8% bands;
   - take the union bbox of remaining text blocks;
   - expand it by 24 PDF points on each side;
   - clip the result to the page-safe region.
3. Otherwise, use the page-safe region directly.

The sparse-text fallback is intentional. It does not infer a narrow body region
from insufficient text evidence.

Repeated-header/footer suppression is applied after this region is calculated;
it can reject stable edge decorations but cannot shrink the body region.

### 4.2 Labeled calibration set

Thresholds are initial values, not permanent truths. Before implementation is
accepted, add:

- `tests/fixtures/visual_decision/cases.json`
- deterministic generated PDFs/images under the same fixture directory;
- `scripts/visual_decision_eval.py`

The labeled set must contain at least:

- fragmented single engineering plot: retain;
- fragmented multi-panel plots: retain as separate or correctly grouped regions;
- direct large figure block: retain;
- native text plus fragmented plot: retain native body and figure asset;
- occasional scanned page: full-page OCR branch;
- sparse cover/divider page: do not misclassify as scanned evidence;
- isolated tiny marks: discard;
- repeated page-header logo: discard;
- repeated footer/page ornament: discard;
- body watermark: reject or defer, never treat as primary evidence;
- uncertain isolated candidate: Level 2.

The committed fixture is the automated calibration gate. Real-corpus cases are
an additional manual regression set, identified by document SHA256 and page
number:

- Zhao Xiaoping thesis pages 25, 77, and 78: retain plots;
- B&K order-analysis page 65: malformed bbox must not abort parsing.

Every threshold change must update the fixture evaluation record. Thresholds
must not be tuned only against the three inspected Zhao pages.

## 5. Page-Level Decisions

### 5.1 Decision precedence

Apply exactly one primary page route:

```text
1. Calculate page features.
2. Evaluate suspected scanned page.
3. If scanned:
     run full-page OCR;
     skip cluster recovery;
     continue to chunking.
4. Otherwise:
     preserve native text;
     run direct-image and tiny-cluster recovery;
     continue to chunking.
```

### 5.2 Occasional scanned page

Current candidate rule:

```text
meaningful_text_chars < 15
AND longest meaningful text block <= 8 chars
AND (
  largest visual region covers >= 50% of the page
  OR aggregate visual occupancy covers >= 65% of the page-safe region
)
```

After all pages are parsed once:

- a document is text-layered when at least 70% of pages contain 50 meaningful
  characters, or median page text is at least 150 meaningful characters;
- in a text-layered document, only a page with zero meaningful characters may
  enter full-page OCR;
- recurring page-backing rasters on at least three and at least 50% of pages are
  excluded from scanned-page evidence;
- OCR fills an empty page body and never replaces usable native text.

This rule must remain configurable only through existing ingestion settings,
not through a new general-purpose rule engine.

For a scanned-page candidate:

1. Render the full page once.
2. Run PaddleOCR.
3. Run Tesseract only when Paddle is empty, has no confidence, fails, or falls
   below the configured confidence threshold.
4. Use the selected OCR result as page body text.
5. Mark `fallback_used`, confidence, and `needs_review`.
6. Do not append OCR text to an already-equivalent native text body.

Low native text alone is insufficient: covers, divider pages, and intentionally
sparse pages must not automatically become OCR pages.

Repeated header/footer regions and isolated edge decorations do not count toward
this visual occupancy.

### 5.3 Fragmented large figure

Initial cluster candidate rule:

```text
tiny block count >= 20
cluster width >= 40 PDF points
cluster height >= 40 PDF points
cluster area >= 1% of page area
cluster overlaps the body region
```

Use a deterministic occupancy-grid connected-component algorithm:

- fixed grid origin: page coordinate `(0, 0)`;
- initial cell size: 4 PDF points;
- relation to the current tiny-block guard: one cell equals the minimum retained
  direct-image dimension;
- relation to 220 DPI rendering: 4 points is approximately 12 rendered pixels;
- mark every cell intersected by a tiny-block bbox;
- apply one-cell 8-neighbor dilation to bridge small drawing gaps;
- find 8-connected occupied components;
- traverse cells in row-major order and sort final components by
  `(top, left, bottom, right)` for deterministic output.

Cell size is a calibration parameter. The fixture evaluation must compare at
least 2, 4, and 8 PDF-point candidates. Four points is the initial default, not
an unreviewable constant.

For each accepted cluster:

1. Expand the cluster bbox by a small bounded margin.
2. Clip it to the page.
3. Render the bbox directly from the original PDF page.
4. Create one figure or table asset regardless of OCR yield.
5. Optionally run region OCR through Paddle/Tesseract routing within the page OCR
   budget.
6. Attach:
   - cluster statistics;
   - rendered asset path;
   - OCR text;
   - confidence and review state;
   - source block count;
   - page and bbox provenance.

The system must render the region from the page. It must not stitch thousands
of fragment PNG files.

### 5.4 Cluster ranking and overflow

Rank accepted candidates by:

```text
score =
  area_ratio
  * clamp(density, 0.1, 1.0)
  * log2(source_block_count + 1)
  * clamp(body_overlap_ratio, 0.1, 1.0)
```

Apply penalties before ranking:

- repeated header/footer signature: reject;
- region wholly outside the body region: reject;
- edge-only overlap: multiply score by 0.25.

Sort by descending score, then `(top, left, bottom, right)`.

Initial retained-cluster limit is 16 per page. This is a tunable calibration
parameter intended to cover genuine multi-panel pages. A hard emergency ceiling
of 24 prevents unbounded output. Candidates beyond the retained limit become
Level 2 summaries and produce a page warning; they are not silently discarded.

### 5.5 Region OCR budget

Region OCR enriches metadata; it does not decide retention.

- retain an accepted visual asset even when OCR is skipped or returns no text;
- OCR at most four retained regions per page by default;
- prioritize regions with adjacent figure/table captions, then larger area,
  then the cluster ranking order;
- record `ocr_status=not_selected`, `ok`, `empty`, or `failed`;
- do not run Tesseract unless Paddle meets the existing fallback condition.

The OCR budget and selection count are calibration targets. Full-page OCR does
not share this budget because scanned-page routing skips cluster recovery.

### 5.6 Isolated decoration

Probable decoration includes:

- tiny blocks outside all accepted clusters;
- blocks confined to repeated header/footer regions;
- repeated cross-page visual signatures;
- tiny isolated marks with negligible body-region overlap.

These blocks produce no PNG and no database asset.

OCR returning no text is not, by itself, grounds for deletion. A valid spectrum
or orbit plot may contain little machine-readable text.

### 5.7 Repeated header/footer detection

Repeated decoration detection is a bounded document-level second pass:

1. Consider only candidates wholly inside the top or bottom 8% page bands.
2. Normalize bbox coordinates by page width/height and quantize them to 1% bins.
3. Build a signature from:
   - top/bottom band;
   - quantized bbox;
   - direct-image versus tiny-cluster origin;
   - quantized aspect ratio.
4. Mark a signature repeated when it occurs on at least three pages and on at
   least 50% of eligible document pages.
5. Repeated candidates are Level 1 unless the page is the document cover/title
   page, where they become Level 2.

No image file is required to build this signature. A later implementation may
add a perceptual hash only if geometry produces demonstrated false matches.
Body-region watermarks are not covered by this edge rule; they remain Level 2
unless the labeled calibration set justifies a deterministic rejection rule.

## 6. Three-Level Asset Policy

### Level 1: discard

Discard only when evidence is jointly sufficient:

- invalid or non-finite bbox;
- zero/negative area;
- isolated microscopic block;
- repeated header/footer decoration;
- outside accepted clusters and outside meaningful body regions;
- no useful OCR signal when the region is also small and non-semantic.

Record aggregate counts and reasons in page metadata. Do not record one metadata
row per discarded fragment.

### Level 2: deferred diagnostic

Use for isolated but uncertain regions:

- do not create database rows;
- do not include them in retrieval;
- do not export individual images;
- keep bounded page-level summaries sufficient for debugging;
- optionally keep a rendered candidate only when an explicit diagnostic mode is
  enabled.

Level 2 is debug-only in v1. There is no automatic promotion path. An explicit
diagnostic mode may render at most four Level-2 candidates per document for
manual inspection; normal ingestion stores only bounded aggregate summaries.
Promotion/review tooling is deferred until real operation demonstrates a need.

### Level 3: retained evidence

Retain:

- normal large image blocks;
- accepted tiny-block clusters;
- suspected scanned pages;
- probable screenshots, tables, flowcharts, spectra, or engineering plots;
- regions with useful OCR text;
- visually meaningful large regions even when OCR text is empty.

## 7. Double-Recovery Mechanism

Two independent recovery paths are required:

1. **Full-page recovery**
   - for occasional scanned pages;
   - OCR output becomes page body content.

2. **Cluster-region recovery**
   - for native/mixed pages with fragmented figures;
   - native text remains page body content;
   - region OCR belongs to the figure/table asset and must not duplicate body
     text.

Both paths use PaddleOCR first and Tesseract fallback. Tesseract failure must not
discard usable Paddle or native text.

## 8. Safety Limits

Initial limits:

- default maximum 16 retained cluster regions per page;
- hard emergency ceiling 24 cluster regions per page;
- maximum four region-OCR calls per page;
- maximum one full-page OCR pass per page;
- no individual export for tiny blocks;
- maximum 100 direct non-tiny image assets per page;
- bounded cluster margin;
- page-level aggregate diagnostics instead of per-fragment JSON;
- deterministic processing order.

If a limit is reached, fail visibly through metadata/warnings while continuing
to preserve readable native text.

### 8.1 Initial parameter table

| Parameter | Initial value | Calibration requirement |
| --- | ---: | --- |
| Direct-image minimum dimension | 4 pt | Preserve normal figures; reject fragment explosion |
| Occupancy grid cell | 4 pt | Compare 2/4/8 pt on labeled cases |
| Minimum cluster blocks | 20 | Tune retain/reject fixture precision |
| Minimum cluster width/height | 40 pt | Tune against small valid plots |
| Minimum cluster page area | 1% | Tune against ornaments and small diagrams |
| Scanned meaningful-text ceiling | 15 chars | Near-absence gate, not sparse-page gate |
| Longest meaningful block ceiling | 8 chars | Preserve sparse but usable native evidence |
| Scanned region coverage | 50% | Test mixed and full-scan pages |
| Scanned aggregate safe-region occupancy | 65% | Test fragmented scanned pages |
| Retained clusters per page | 16 | Multi-panel fixture must retain all labeled panels |
| Hard cluster ceiling | 24 | Safety-only; overflow must warn |
| Region OCR calls per page | 4 | Measure OCR cost and metadata yield |
| Direct non-tiny assets per page | 100 | Safety-only |

No parameter is changed without recording labeled-set results.

## 9. Development Steps

### Step 0: governance

Files:

- `docs/phase_4_migrations.md`
- `docs/phase_4_interface_freeze.md`

Changes:

- record the page-level visual recovery behavior change;
- state that page/chunk text and asset outputs require re-ingestion;
- provide rollback to native text plus direct large-image extraction.

Verification:

- migration and freeze notes exist before production callers change.

### Step 1: page feature analysis

Files:

- new focused module under `src/vibration_agent/ingestion/`, for example
  `page_visual_analysis.py`;
- `src/vibration_agent/ingestion/pymupdf_parser.py`;
- focused unit tests.

Changes:

- collect text/image block features without exporting images;
- calculate bounded union coverage and body-region overlap;
- aggregate skipped-fragment diagnostics.

Verification:

- feature extraction on a 30,000-fragment page completes without quadratic
  behavior or file writes.
- body-region behavior is tested for dense text, sparse text, covers, and scanned
  pages.

### Step 1.5: calibration fixture and evaluator

Files:

- `tests/fixtures/visual_decision/cases.json`;
- deterministic fixture generator/assets;
- `scripts/visual_decision_eval.py`;
- evaluator unit tests.

Changes:

- define expected page route, retained regions, rejected decorations, and
  tolerated bbox ranges;
- report must-retain recall, decoration rejection, scanned-page route accuracy,
  and region over-splitting/over-merging.

Verification:

- baseline emergency guard fails the fragmented-plot retain cases;
- the evaluator is deterministic across two runs;
- no production threshold is changed without an attached evaluator result.

### Step 2: spatial clustering

Files:

- the page visual analysis module;
- clustering tests and synthetic fixtures.

Changes:

- implement grid-based connected components;
- reject isolated decorations;
- return bounded candidate regions.
- implement deterministic score/ranking and Level-2 overflow summaries.

Verification:

- synthetic fragmented plots merge into expected regions;
- separated figures remain separate;
- header/footer fragments do not merge into body figures.

### Step 3: region rendering and OCR

Files:

- `pymupdf_parser.py`;
- OCR router integration;
- asset mapping tests.

Changes:

- render accepted cluster bboxes from the page;
- route only the bounded selected regions through Paddle/Tesseract;
- store OCR result on the asset only.

Verification:

- no fragment PNGs are created;
- each accepted cluster creates at most one rendered image and one asset.
- accepted regions survive empty or skipped OCR.

### Step 4: occasional scanned-page fallback

Files:

- page parser/pipeline;
- OCR router;
- mixed-document tests.

Changes:

- trigger full-page OCR from page features;
- replace insufficient native body text with OCR text;
- preserve native text on ordinary mixed pages.

Verification:

- a native document containing one scanned page recovers that page without
  sending the entire document through OCR.

### Step 5: repeated decoration detection

Files:

- page visual analysis module;
- document-level parsing coordinator.

Changes:

- build bounded signatures for stable header/footer regions;
- suppress repeated decorative candidates across pages.

Verification:

- repeated logos/watermarks do not become hundreds of assets;
- unique body figures remain retained.

### Step 6: persistence and chunk integration

Files:

- existing asset/chunk mappings only where required;
- storage and chunking tests.

Changes:

- retained region assets flow into chunks and Postgres;
- Level 1 and Level 2 candidates do not enter Qdrant;
- page OCR body text remains embeddable.

Verification:

- PG/Qdrant equality remains `points == embeddable_chunks`;
- asset-only records do not create empty vector points.

### Step 7: real-corpus regression and re-ingestion

Fixtures/cases:

- Zhao Xiaoping thesis pages 25, 77, 78;
- B&K order-analysis PDF;
- one native text-only PDF;
- one scanned PDF;
- one mixed native/scanned fixture.

Changes:

- stop and clear the current partial full-ingestion run;
- regenerate all local artifacts and runtime stores;
- run full ingestion only after all gates pass.

This refinement gates full ingestion. The emergency guard prevents file
explosion but drops clustered engineering figures. Completing full ingestion
before this refinement would knowingly build an incomplete visual knowledge base
and require another full reset/re-ingestion.

## 10. Acceptance Rules

### Correctness

- Native body text on mixed pages is preserved.
- Occasional scanned-page OCR text becomes page content.
- A page takes exactly one primary route: scanned-page recovery or native/mixed
  cluster recovery.
- Cluster OCR text belongs to the visual asset, not duplicated body text.
- Useful plots remain retained even when OCR returns no text.
- Invalid or decorative fragments do not become assets.

### Real failure case

For the Zhao Xiaoping thesis:

- no more than the configured retained-cluster limit is emitted per page;
- total local image files remain bounded and reviewable;
- pages 25, 77, and 78 retain their engineering plots as visual assets;
- the original 334,422 blocks do not produce per-block files or rows;
- parser runtime is minutes at most, not an unbounded file-writing loop;
- page metadata reports aggregate filtered-fragment counts.

### Normal-document regression

For B&K order analysis:

- valid figures remain available;
- the malformed page-65 bbox does not abort ingestion;
- readable text and chunks remain unchanged except for intentional asset
  metadata additions.

### OCR behavior

- Paddle is primary.
- Tesseract runs only under fallback conditions.
- fallback failure preserves native/Paddle results and marks review.
- no page receives duplicate full-page OCR.

### Performance and storage

- clustering is not O(n²);
- the 30,000-fragment fixture completes within a test-defined bounded runtime
  relative to a 3,000-fragment fixture; no absolute cross-machine benchmark is
  used as the only gate;
- no tiny image block is exported individually;
- no page exceeds configured candidate/asset limits;
- diagnostic metadata size is proportional to pages/clusters, not fragments;
- full ingestion produces no six-figure file count for one document.

### Tests and gates

- labeled visual-decision fixtures include both must-retain and must-reject cases;
- must-retain recall is 100% on the initial labeled set;
- scanned-page route accuracy is 100% on the initial labeled set;
- no repeated header/footer decoration is retained;
- multi-panel fixtures are neither merged into one page-wide region nor truncated
  by the retained-region cap;
- focused feature, clustering, OCR-routing, persistence, and regression tests
  pass;
- tests encode why fragmented plots must be recovered and why decorations must
  be rejected;
- full unit suite passes with no skipped relevant tests;
- PG embeddable chunk count equals Qdrant point count;
- representative rendered assets are manually inspected before approval.

## 11. Deferred Work

VLM figure description is deferred. It may later enrich retained visual assets,
but the first implementation must be complete with deterministic page analysis,
region rendering, PaddleOCR, and Tesseract fallback.

## 12. Review Gate

No implementation beyond the existing emergency anti-explosion guard should
proceed until this revised design is re-reviewed. Review must explicitly approve:

- the labeled calibration set and evaluator contract;
- scanned-page precedence over cluster recovery;
- the 4-point occupancy grid default and 2/4/8 calibration range;
- body-region derivation and sparse-text fallback;
- cluster ranking, default limit 16, and hard ceiling 24;
- bounded optional region OCR;
- Level-2 debug-only lifecycle;
- re-ingestion requirement;
- whether region OCR text is sufficient before any VLM work.

## 13. Review Feedback Closure

- R1: resolved by the labeled visual-decision fixture/evaluator and mandatory
  threshold-result records.
- R2: resolved by the scanned-first exclusive decision tree.
- R3: resolved by the deterministic 4-point grid, fixed origin, 8-connectivity,
  one-cell dilation, and 2/4/8 calibration.
- R4: resolved by explicit text-supported body bounds plus page-safe sparse-text
  fallback.
- R5: resolved by deterministic scoring, default top 16, hard ceiling 24, and
  Level-2 overflow warnings.
- R6: resolved by making region OCR additive and limiting it to four regions per
  page.
- R7: resolved by declaring Level 2 debug-only in v1 with no automatic promotion.

## 14. Implementation Verification

Implemented on 2026-06-25:

- deterministic page feature analysis and body-region derivation;
- 4-point occupancy-grid clustering with bounded connected components;
- scanned-page-first exclusive routing;
- direct and fragmented visual-region rendering;
- bounded region OCR with PaddleOCR and Tesseract fallback;
- repeated header/footer suppression and Level-2 aggregate diagnostics;
- labeled visual-decision fixtures and evaluator;
- Qdrant document-point replacement before re-ingest upsert.

Verification:

- labeled visual-decision evaluation: 11/11 passed;
- focused implementation tests: 38 passed;
- unit suite: 500 passed;
- implementation-review focused tests: 7 passed;
- full non-large-corpus suite after implementation review: 524 passed;
- 3,000-fragment analysis: approximately 0.0028 seconds;
- 30,000-fragment analysis: approximately 0.0351 seconds;
- measured 30,000/3,000 runtime ratio: 12.44x, replacing the reviewed
  quadratic 99x path with bounded near-linear growth;
- live region OCR: PaddleOCR, 673 characters, average confidence 0.975,
  no fallback, approximately 20.6 seconds;
- Zhao Xiaoping thesis: 147 pages, 79 recovered cluster assets, 139 visual
  files total; pages 25/77/78 recovered 3/4/4 clusters; approximately 33.2
  seconds without OCR;
- B&K order-analysis PDF: 65 pages, 53 visual files, malformed page-65 bbox
  recorded and skipped without abort; approximately 1.4 seconds.

Step 7 remains destructive and has not been run: generated local artifacts,
Postgres ingestion rows, and Qdrant points must be cleared before the final
full-corpus ingestion.

## 15. Implementation Review Closure

Closed on 2026-06-25:

- I1: replaced list-membership tiny/direct partitioning with one linear pass;
- I2: added a 30,000-versus-3,000 fragment relative-ratio regression test;
- I3: expanded the labeled set from 5 to all 11 required decision categories,
  including repeated edge decorations, deferred watermark fragments, a direct
  figure, and native text with a fragmented plot;
- I4: evaluator now checks cluster bboxes with tolerances, direct retained
  images, deferred tiny-fragment counts, repeated-decoration rejection, and the
  emergency-guard negative control.

The implementation-review blockers are closed. Step 7 clean re-ingestion and
the database/vector parity checks remain operational acceptance work.

## 16. Native Ingestion Performance Closure

Closed on 2026-06-25:

- confirmed page visual analysis was not the dominant regression;
- removed the R2 analysis pre-pass that called
  `page.get_text("dict", sort=True)` twice per page;
- each page dictionary is now extracted once and reused for feature analysis
  and block processing;
- edge-band assets are held as bounded metadata candidates, then rendered only
  when the document-level repeated-decoration filter accepts them;
- region OCR runs after that filter, preserving its page budget and avoiding OCR
  on rejected decoration;
- region OCR is independently configurable and disabled by default for bulk
  native ingestion; visual assets remain retained and low-text scanned pages
  still receive full-page OCR;
- fragment-heavy page dictionaries are not cached across the document.

Verification:

- parser regression explicitly asserts one dictionary extraction per page;
- unique edge images remain rendered, while repeated header images create no
  PNG files or retained assets;
- focused visual/parser suite: 21 passed;
- labeled visual decision evaluation: 11/11 passed;
- full non-large-corpus suite: 526 passed.

The original ORBIT 60 profiling document was not present under `data/raw` during
this closure, so its reported 104 ms/page saving has not been independently
re-profiled. The one-call-per-page invariant is automated; a real-corpus timing
sample remains part of Step 7 operational acceptance.

## 17. OCR-Overlay Page Raster Closure

Closed on 2026-06-25 after inspecting
`发动机变速阶段振动信号阶比跟踪研究_孔庆鹏.pdf`:

- the 113-page PDF contains one scan/background raster per page plus an OCR text
  layer; these page carriers are not 113 engineering figures;
- page-backing images are now identified by at least 80% page coverage and
  contact with at least two page edges;
- when the native/OCR text layer is sufficient, the backing raster is excluded
  from visual analysis, asset rendering, persistence, and region OCR;
- when text is insufficient, the raster remains available to trigger the
  exclusive full-page OCR route;
- local body figures remain retained independently.

Real-document calibration:

- page-backing rasters detected: 113/113;
- local image blocks retained as candidates: 18;
- low-text pages previously misrouted to full-page OCR: 5;
- no-OCR structural parse: approximately 10.1 seconds for 113 pages;
- default region OCR calls during bulk native ingestion: 0.

Verification:

- focused parser/config/visual tests: 33 passed;
- labeled visual decision evaluation: 11/11 passed;
- full non-large-corpus suite: 529 passed.

## 18. Scanned-Page Misroute Closure

Closed on 2026-06-25:

- replaced the 100-character sparsity gate with near-absence and meaningful
  text-block gates;
- added a document-level text-layer profile without restoring a second
  `get_text()` pass;
- recurring sandwich/page-backing rasters no longer count as scanned evidence;
- full-page OCR is decided after the single native parsing pass;
- usable native blocks are never replaced by OCR output;
- a unique zero-text scan inside a text-layered native document still receives
  full-page OCR.

Real-document calibration for the 113-page Kong Qingpeng paper:

- native routes: 113;
- scanned-page OCR routes: 0;
- OCR calls: 0;
- structural parse time: approximately 8.36 seconds.

Verification:

- focused parser/config/visual tests: 36 passed;
- labeled visual decision evaluation: 12/12 passed.
