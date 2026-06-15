"""Skill registry.

URGENT (phase-0):
  S1 ingestion, S2 retrieval, S3 qa_summary, V2 citation_check, V4 style

Optional:
  V1 term_symbol_unit_normalizer, S4 engineering_analysis, S5 formula_derivation, V3 reviewer

Default-off Phase-4 prototype:
  S6 literature_search

Deferred:
  S7 model_selection, S8 experiment_advice
"""
from .base import Skill
from .s4_engineering_analysis import EngineeringAnalysisSkill
from .s5_formula_derivation import FormulaDerivationSkill
from .s1_ingestion import IngestionSkill
from .s2_retrieval import RetrievalSkill
from .s3_qa_summary import QASummarySkill
from .v1_term_symbol_unit_normalizer import TermSymbolUnitNormalizerSkill
from .v2_citation_check import CitationCheckSkill
from .v3_reviewer import ReviewerSkill
from .v4_style import OutputStyleSkill

__all__ = [
    "CitationCheckSkill",
    "EngineeringAnalysisSkill",
    "FormulaDerivationSkill",
    "IngestionSkill",
    "LiteratureSearchSkill",
    "OutputStyleSkill",
    "QASummarySkill",
    "ReviewerSkill",
    "RetrievalSkill",
    "Skill",
    "TermSymbolUnitNormalizerSkill",
]


def __getattr__(name: str):
    if name == "LiteratureSearchSkill":
        from .s6_literature_search import LiteratureSearchSkill

        return LiteratureSearchSkill
    raise AttributeError(name)
