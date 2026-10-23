"""Deterministic mock provider for tests and local demos (no API cost)."""
from __future__ import annotations

from app.ai.base import GenerationResult, GenerationSpec, QuestionProvider


class MockProvider(QuestionProvider):
    name = "mock"

    async def generate(self, spec: GenerationSpec) -> GenerationResult:
        topic = (spec.topics[0] if spec.topics else spec.subject) or "general"
        candidates: list[dict] = []
        for i in range(spec.count):
            candidates.append(self._one(spec.question_type, topic, i, spec.difficulty))
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        return GenerationResult(candidates=candidates, model="mock-1", usage=usage)

    @staticmethod
    def _one(qtype: str, topic: str, i: int, difficulty: str) -> dict:
        base = {"difficulty": difficulty, "marks": 1}
        if qtype == "numerical":
            return {
                **base,
                "type": "numerical",
                "text": f"[AI] Compute value {i} for {topic}",
                "numerical_answer": str(float(i) + 0.5),
                "numerical_tolerance": "0.01",
            }
        if qtype == "true_false":
            return {
                **base,
                "type": "true_false",
                "text": f"[AI] Statement {i} about {topic} is correct.",
                "options": [
                    {"text": "True", "is_correct": i % 2 == 0},
                    {"text": "False", "is_correct": i % 2 == 1},
                ],
            }
        if qtype == "multi_mcq":
            return {
                **base,
                "type": "multi_mcq",
                "text": f"[AI] Select all that apply for {topic} ({i})",
                "options": [
                    {"text": f"Opt A{i}", "is_correct": True},
                    {"text": f"Opt B{i}", "is_correct": True},
                    {"text": f"Opt C{i}", "is_correct": False},
                    {"text": f"Opt D{i}", "is_correct": False},
                ],
            }
        # default: single_mcq
        return {
            **base,
            "type": "single_mcq",
            "text": f"[AI] Question {i} about {topic}",
            "options": [
                {"text": f"Choice A{i}", "is_correct": True},
                {"text": f"Choice B{i}", "is_correct": False},
                {"text": f"Choice C{i}", "is_correct": False},
                {"text": f"Choice D{i}", "is_correct": False},
            ],
        }
