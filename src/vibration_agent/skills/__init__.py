"""Skill registry.

URGENT (phase-0):
  S1 ingestion, S2 retrieval, S3 qa_summary, V2 citation_check, V4 style

Optional:
  V1 term_symbol_unit_normalizer, S4 engineering_analysis, V3 reviewer

Deferred:
  S5 formula_derivation, S6 literature, S7 model_selection, S8 experiment_advice
"""
from .base import Skill
from .s4_engineering_analysis import EngineeringAnalysisSkill
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
    "IngestionSkill",
    "OutputStyleSkill",
    "QASummarySkill",
    "ReviewerSkill",
    "RetrievalSkill",
    "Skill",
    "TermSymbolUnitNormalizerSkill",
]
