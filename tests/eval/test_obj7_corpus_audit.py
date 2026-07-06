import json
import subprocess
import sys
from pathlib import Path

from scripts.obj7_corpus_audit import run_obj7_corpus_audit


def _write_taxonomy(root: Path, aliases: list[dict]) -> None:
    root.mkdir()
    root.joinpath("retrieval_aliases.yaml").write_text(
        "schema_version: phase5.retrieval_aliases.v1\n"
        "families:\n"
        + "\n".join(
            "\n".join(
                [
                    f"  - id: {row['id']}",
                    *(
                        f"    {key}: {json.dumps(value, ensure_ascii=False)}"
                        for key, value in row.items()
                        if key != "id"
                    ),
                ]
            )
            for row in aliases
        )
        + "\n",
        encoding="utf-8",
    )


def test_obj7_audit_separates_direct_source_metadata_from_fallback(tmp_path):
    taxonomy = tmp_path / "taxonomy"
    _write_taxonomy(taxonomy, [{"id": "critical_speed", "aliases": ["critical speed", "resonance"]}])
    chunks = [
        {
            "chunk_id": "c1",
            "doc_id": "doc_a",
            "source_filename": "a.pdf",
            "source_title": "A",
            "source_path": "data/raw/a.pdf",
            "text": "plain text",
        },
        {
            "chunk_id": "c2",
            "doc_id": "doc_b",
            "title": "B",
            "source_path": "data/raw/b.pdf",
            "text": "plain text",
        },
        {"chunk_id": "document_abc_p0001_00001", "doc_id": "document_abc", "text": "plain text"},
    ]
    report = run_obj7_corpus_audit(
        chunks=chunks,
        questions={"cases": []},
        taxonomy_dir=taxonomy,
        sample_limit=5,
    )

    assert report["source_metadata"]["direct_source_filename_count"] == 1
    assert report["source_metadata"]["fallback_source_filename_count"] == 2
    assert report["source_metadata"]["direct_source_title_count"] == 1
    assert report["source_metadata"]["fallback_source_title_count"] == 2
    assert report["source_metadata"]["generic_identity_count"] == 1
    assert report["source_metadata"]["generic_user_facing_identity_count"] == 0
    assert report["source_metadata"]["generic_internal_identity_count"] == 1
    assert report["mutation_prerequisites"]["requires_source_metadata_migration"] is True
    assert report["mutation_prerequisites"]["requires_generic_document_review"] is False


def test_obj7_audit_flags_mojibake_and_key_fact_alias_gaps(tmp_path):
    taxonomy = tmp_path / "taxonomy"
    _write_taxonomy(
        taxonomy,
        [
            {
                "id": "critical_speed",
                "canonical": "critical speed",
                "aliases": ["critical speed", "resonance"],
                "languages": ["en"],
                "source_miss_case_ids": ["case1"],
                "ambiguity": "Use with rotor critical-speed questions.",
            },
            {"id": "broken_alias", "aliases": ["锛", "garbled"]},
        ],
    )
    questions = {
        "schema_version": "test",
        "cases": [
            {
                "case_id": "case1",
                "key_facts": [
                    {"fact_id": "covered", "aliases": ["critical speed"]},
                    {"fact_id": "missing", "aliases": ["axial vibration"]},
                ],
                "expected_evidence": [
                    {"doc_id": "document_abc", "chunk_id": "document_abc_p0001_00001"}
                ],
            }
        ],
    }
    report = run_obj7_corpus_audit(
        chunks=[
            {"chunk_id": "c1", "doc_id": "doc_a", "source_filename": "a.pdf", "source_title": "A", "text": "normal"},
            {"chunk_id": "c2", "doc_id": "doc_b", "source_filename": "b.pdf", "source_title": "B", "text": "闃诲凹姣 鍥烘湁棰戠巼 锛"},
            {
                "chunk_id": "document_abc_p0001_00001",
                "doc_id": "document_abc",
                "source_filename": "order-analysis.pdf",
                "source_title": "Order Analysis",
                "text": "normal",
            },
        ],
        questions=questions,
        taxonomy_dir=taxonomy,
        sample_limit=5,
    )

    assert report["mojibake"]["chunk_mojibake_count"] == 1
    assert report["mojibake"]["field_counts"]["text"] == 1
    assert report["taxonomy"]["retrieval_aliases"]["mojibake_alias_count"] == 1
    assert report["taxonomy"]["retrieval_aliases"]["traceable_family_count"] == 1
    assert report["taxonomy"]["retrieval_aliases"]["trace_metadata_issue_samples"] == []
    assert report["taxonomy"]["key_fact_alias_coverage"]["covered_alias_count"] == 1
    assert report["taxonomy"]["key_fact_alias_coverage"]["missing_alias_samples"] == [
        {"case_id": "case1", "fact_id": "missing", "alias": "axial vibration"}
    ]
    assert report["obj1_expected_evidence"]["generic_expected_doc_ids"] == ["document_abc"]
    assert report["obj1_expected_evidence"]["generic_expected_unresolved_samples"] == []


def test_obj7_audit_flags_user_facing_generic_identity_and_unresolved_expected_evidence(tmp_path):
    taxonomy = tmp_path / "taxonomy"
    _write_taxonomy(taxonomy, [{"id": "critical_speed", "aliases": ["critical speed"]}])
    questions = {
        "cases": [
            {
                "case_id": "case1",
                "key_facts": [],
                "expected_evidence": [
                    {"doc_id": "document_missing", "chunk_id": "document_missing_p0001_00001"}
                ],
            }
        ]
    }

    report = run_obj7_corpus_audit(
        chunks=[
            {
                "chunk_id": "document_abc_p0001_00001",
                "doc_id": "document_abc",
                "source_filename": "document_abc.pdf",
                "source_title": "document_abc",
                "source_path": "data/raw/document_abc.pdf",
                "text": "plain text",
            }
        ],
        questions=questions,
        taxonomy_dir=taxonomy,
        sample_limit=5,
    )

    assert report["source_metadata"]["generic_user_facing_identity_count"] == 1
    assert report["obj1_expected_evidence"]["generic_expected_unresolved_samples"] == [
        {
            "case_id": "case1",
            "doc_id": "document_missing",
            "chunk_id": "document_missing_p0001_00001",
        }
    ]
    assert report["mutation_prerequisites"]["requires_generic_document_review"] is True


def test_obj7_audit_cli_writes_report_without_project_pythonpath(tmp_path):
    taxonomy = tmp_path / "taxonomy"
    _write_taxonomy(taxonomy, [{"id": "critical_speed", "aliases": ["critical speed", "resonance"]}])
    questions = tmp_path / "questions.json"
    questions.write_text(json.dumps({"schema_version": "test", "cases": []}), encoding="utf-8")
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(
        json.dumps(
            {
                "chunk_id": "c1",
                "doc_id": "doc_a",
                "source_filename": "a.pdf",
                "source_title": "A",
                "source_path": "data/raw/a.pdf",
                "text": "plain text",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/obj7_corpus_audit.py",
            "--source",
            "chunks",
            "--chunk-path",
            str(chunks),
            "--questions",
            str(questions),
            "--taxonomy-dir",
            str(taxonomy),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == "phase5.obj7.corpus_audit.report.v1"
    assert report["corpus"]["chunk_count"] == 1
