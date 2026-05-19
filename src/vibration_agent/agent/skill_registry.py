"""Vendor-neutral agent skill registry.

The registry reads project-owned `SKILL.md` packages. It does not depend on
Anthropic-native Skills or OpenAI-native tool definitions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AgentSkill(BaseModel):
    skill_id: str
    path: Path
    title: str
    description: str = ""
    body: str
    references: list[Path] = Field(default_factory=list)
    scripts: list[Path] = Field(default_factory=list)


def _title_from(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _description_from(body: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("# "):
            for candidate in lines[index + 1 :]:
                candidate = candidate.strip()
                if candidate:
                    return candidate
    return ""


def _default_root() -> Path:
    from vibration_agent.config import load

    return load().paths.workspace / "agent_skills"


class AgentSkillRegistry(BaseModel):
    root: Path
    skills: dict[str, AgentSkill] = Field(default_factory=dict)

    @classmethod
    def load(cls, root: str | Path | None = None) -> "AgentSkillRegistry":
        root_path = Path(root).resolve() if root is not None else _default_root().resolve()
        skills: dict[str, AgentSkill] = {}
        if not root_path.exists():
            return cls(root=root_path, skills=skills)
        for skill_file in sorted(root_path.glob("*/SKILL.md")):
            skill_id = skill_file.parent.name
            body = skill_file.read_text(encoding="utf-8-sig")
            references = sorted((skill_file.parent / "references").glob("**/*")) if (skill_file.parent / "references").exists() else []
            scripts = sorted((skill_file.parent / "scripts").glob("**/*")) if (skill_file.parent / "scripts").exists() else []
            skills[skill_id] = AgentSkill(
                skill_id=skill_id,
                path=skill_file.resolve(),
                title=_title_from(body, skill_id),
                description=_description_from(body),
                body=body,
                references=[path.resolve() for path in references if path.is_file()],
                scripts=[path.resolve() for path in scripts if path.is_file()],
            )
        return cls(root=root_path, skills=skills)

    def get(self, skill_id: str) -> AgentSkill:
        try:
            return self.skills[skill_id]
        except KeyError as exc:
            raise KeyError(f"Unknown agent skill: {skill_id}") from exc

    def list_ids(self) -> list[str]:
        return sorted(self.skills)

    def as_prompt_catalog(self) -> list[dict[str, Any]]:
        return [
            {"skill_id": skill.skill_id, "title": skill.title, "description": skill.description, "path": str(skill.path)}
            for skill in sorted(self.skills.values(), key=lambda item: item.skill_id)
        ]
