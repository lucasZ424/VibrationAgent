"""Manual smoke runner for V4 style shaping."""
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills import OutputStyleSkill

s3_result = SkillOutput(
    status="ok",
    summary="S3 qa ok: 1 claim(s) from 1 chunk(s).",
    structured_result={
        "answer": "根据已检索证据，可以确定：\n1. 阻尼越大，振动衰减越快。（证据：c1）",
        "claims": [{"text": "阻尼越大，振动衰减越快。", "chunk_id": "c1", "doc_id": "doc1", "pages": [3]}],
    },
    citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[3])],
)

payload = SkillInput(task_id="manual-v4", user_query="阻尼如何影响振动？", context={"s3_result": s3_result})
print(OutputStyleSkill().run(payload).structured_result["answer"])
