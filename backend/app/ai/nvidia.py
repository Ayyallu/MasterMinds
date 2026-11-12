"""NVIDIA NIM provider adapter (OpenAI-compatible chat completions).

Inert until NVIDIA_API_KEY is configured. Only syllabus/topic/type/difficulty
metadata is ever sent — never student personal data. Secrets and full prompts
are never logged or placed in error messages.

LLM output is loosely structured, so this adapter:
  * requests questions in small batches (keeps responses within token limits),
  * extracts JSON even when wrapped in markdown fences or prose,
  * normalises common field-name variants into the app's candidate shape.
Every candidate is still fully validated by generation_service before storage.
"""
from __future__ import annotations

import asyncio
import json
import re

import httpx

from app.ai.base import (
    GenerationResult,
    GenerationSpec,
    ProviderAuthError,
    ProviderError,
    ProviderNotConfigured,
    ProviderTimeout,
    QuestionProvider,
)
from app.config import get_settings

# Questions requested per API call. Large models take ~8 s per question, so
# pools are split into small batches that run a few at a time.
BATCH_SIZE = 5
CONCURRENCY = 4

_SHAPES = {
    "single_mcq": (
        '{"type": "single_mcq", "text": "...", "options": [{"text": "...", "is_correct": true}, '
        '{"text": "...", "is_correct": false}, ...4 options], "explanation": "...", '
        '"difficulty": "easy|medium|hard", "marks": 1}  // exactly ONE option is_correct'
    ),
    "multi_mcq": (
        '{"type": "multi_mcq", "text": "...", "options": [{"text": "...", "is_correct": true}, ...4-5 options], '
        '"explanation": "...", "difficulty": "easy|medium|hard", "marks": 2}  // TWO OR MORE options is_correct'
    ),
    "true_false": (
        '{"type": "true_false", "text": "<a statement>", "options": [{"text": "True", "is_correct": true}, '
        '{"text": "False", "is_correct": false}], "explanation": "...", "difficulty": "easy|medium|hard", "marks": 1}'
    ),
    "numerical": (
        '{"type": "numerical", "text": "...", "numerical_answer": "12.5", "numerical_tolerance": "0.01", '
        '"explanation": "...", "difficulty": "easy|medium|hard", "marks": 2}  // no options'
    ),
}

_SYSTEM = (
    "You are an expert teacher who writes accurate, unambiguous exam questions. "
    "Respond with ONLY a JSON object of the form {\"questions\": [ ... ]} — no markdown, "
    "no commentary. Every option text within a question must be unique. "
    "Each question object must have exactly this shape:\n"
)


class NvidiaNimProvider(QuestionProvider):
    name = "nvidia"

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.nvidia_api_key.strip():
            raise ProviderNotConfigured(
                "AI provider is 'nvidia' but NVIDIA_API_KEY is not set in backend/.env"
            )

    # ------------------------------------------------------------------ prompt
    def _messages(self, spec: GenerationSpec, count: int, batch_no: int, batches: int) -> list[dict]:
        shape = _SHAPES.get(spec.question_type, _SHAPES["single_mcq"])
        parts = [
            f"Write {count} {spec.difficulty} '{spec.question_type}' question(s).",
            f"Subject: {spec.subject or 'general knowledge'}.",
        ]
        if spec.topics:
            parts.append(f"Topics: {', '.join(spec.topics)}.")
        if spec.grade:
            parts.append(f"Level / grade: {spec.grade}.")
        if batches > 1:
            # Parallel batches can't see each other, so ask each for a different
            # slice of the topic (exact repeats are still de-duplicated server-side).
            parts.append(
                f"This is set {batch_no} of {batches}; cover different sub-topics and "
                "question styles than a typical first set would."
                if batch_no > 1 else f"This is set 1 of {batches}."
            )
        parts.append("Do not include any personal data.")
        return [
            {"role": "system", "content": _SYSTEM + shape},
            {"role": "user", "content": " ".join(parts)},
        ]

    # ------------------------------------------------------------------ http
    async def _complete(self, client: httpx.AsyncClient, messages: list[dict], json_mode: bool) -> dict:
        s = self._settings
        payload: dict = {
            "model": s.nvidia_model,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 6000,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = await client.post(
                f"{s.nvidia_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {s.nvidia_api_key.strip()}"},
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(
                f"NVIDIA NIM did not respond within {s.ai_request_timeout_seconds:.0f}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Could not reach NVIDIA NIM ({type(exc).__name__})") from exc

        if resp.status_code == 200:
            return resp.json()
        raise _http_error(resp.status_code, s.nvidia_model, _detail(resp))

    async def _batch(self, client: httpx.AsyncClient, spec: GenerationSpec, count: int, batch_no: int, batches: int):
        messages = self._messages(spec, count, batch_no, batches)
        try:
            data = await self._complete(client, messages, json_mode=True)
        except _JsonModeUnsupported:
            # Some models reject response_format; the prompt already demands JSON.
            data = await self._complete(client, messages, json_mode=False)
        try:
            content = data["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ProviderError("NVIDIA NIM returned an unexpected response shape") from exc
        items = _extract_questions(content)
        if items is None:
            raise ProviderError("NVIDIA NIM returned text that is not valid question JSON")
        cands = [normalize_candidate(i, spec) for i in items if isinstance(i, dict)]
        return cands[:count], data.get("usage") or {}

    async def generate(self, spec: GenerationSpec) -> GenerationResult:
        sizes = [BATCH_SIZE] * (spec.count // BATCH_SIZE)
        if spec.count % BATCH_SIZE:
            sizes.append(spec.count % BATCH_SIZE)
        gate = asyncio.Semaphore(CONCURRENCY)

        async with httpx.AsyncClient(timeout=self._settings.ai_request_timeout_seconds) as client:

            async def run(i: int, n: int):
                async with gate:
                    return await self._batch(client, spec, n, i + 1, len(sizes))

            results = await asyncio.gather(
                *(run(i, n) for i, n in enumerate(sizes)), return_exceptions=True
            )

        candidates: list[dict] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        errors = [r for r in results if isinstance(r, BaseException)]
        for r in results:
            if isinstance(r, BaseException):
                continue
            batch, u = r
            candidates.extend(batch)
            for k in usage:
                usage[k] += int(u.get(k) or 0)
        if errors and not candidates:
            # Nothing usable: surface the most specific error (auth > other).
            auth = [e for e in errors if isinstance(e, ProviderAuthError)]
            err = (auth or errors)[0]
            if isinstance(err, ProviderError):
                raise err
            raise ProviderError(f"NVIDIA NIM batch failed ({type(err).__name__})") from err
        if errors:
            usage["failed_batches"] = len(errors)
        return GenerationResult(candidates=candidates, model=self._settings.nvidia_model, usage=usage)


# ---------------------------------------------------------------------- errors
class _JsonModeUnsupported(ProviderError):
    pass


def _detail(resp: httpx.Response) -> str:
    """Short, secret-free description from the provider's error body."""
    try:
        body = resp.json()
        msg = body.get("detail") or body.get("title") or body.get("error") or ""
        if isinstance(msg, dict):
            msg = msg.get("message", "")
    except ValueError:
        msg = resp.text
    return str(msg)[:200]


def _http_error(status: int, model: str, detail: str) -> ProviderError:
    if status in (401, 403):
        return ProviderAuthError(
            f"NVIDIA rejected the API key (HTTP {status}). Check that NVIDIA_API_KEY in "
            "backend/.env is a current key from build.nvidia.com with API access, then restart the backend."
        )
    if status in (404, 410):
        return ProviderAuthError(
            f"NVIDIA model '{model}' is not available (HTTP {status}"
            f"{': ' + detail if detail else ''}). Set NVIDIA_MODEL in backend/.env to a current model."
        )
    lowered = detail.lower()
    if status in (400, 422) and ("response_format" in lowered or "json" in lowered):
        return _JsonModeUnsupported(f"Model rejected JSON mode (HTTP {status})")
    if status == 429:
        return ProviderError("NVIDIA NIM rate limit reached (HTTP 429). Try again shortly.")
    if status >= 500:
        return ProviderError(f"NVIDIA NIM server error (HTTP {status}). Try again shortly.")
    return ProviderAuthError(f"NVIDIA NIM request was rejected (HTTP {status}{': ' + detail if detail else ''})")


# ---------------------------------------------------------------------- parsing
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


def _extract_questions(content: str) -> list | None:
    """Pull the question list out of model text, tolerating fences/prose."""
    candidates = [content.strip()]
    candidates += [m.strip() for m in _FENCE.findall(content)]
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start, end = content.find(open_ch), content.rfind(close_ch)
        if start != -1 and end > start:
            candidates.append(content[start : end + 1])
    for text in candidates:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("questions", "items", "data", "results"):
                if isinstance(parsed.get(key), list):
                    return parsed[key]
            if "text" in parsed or "question" in parsed:
                return [parsed]
    return None


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() in {"true", "yes", "1", "correct", "y"}


def _num_str(v) -> str | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return repr(float(v)) if isinstance(v, float) else str(v)
    m = re.search(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?", str(v).replace(",", ""))
    return m.group(0) if m else None


def normalize_candidate(raw: dict, spec: GenerationSpec) -> dict:
    """Map common LLM variants onto the QuestionCreate shape. Validation of the
    result (answer keys, option counts, etc.) happens in generation_service."""
    qtype = spec.question_type
    text = raw.get("text") or raw.get("question") or raw.get("prompt") or raw.get("stem") or ""
    out: dict = {
        "type": qtype,
        "text": str(text).strip(),
        "difficulty": str(raw.get("difficulty") or spec.difficulty).strip().lower(),
    }
    if out["difficulty"] not in {"easy", "medium", "hard"}:
        out["difficulty"] = spec.difficulty
    try:
        out["marks"] = max(1, int(float(raw.get("marks") or 1)))
    except (TypeError, ValueError):
        out["marks"] = 1
    expl = raw.get("explanation") or raw.get("rationale") or raw.get("solution")
    if expl:
        out["explanation"] = str(expl).strip()[:4000]

    answer = raw.get("answer", raw.get("correct_answer", raw.get("correct")))

    if qtype == "numerical":
        out["numerical_answer"] = _num_str(raw.get("numerical_answer", answer))
        tol = _num_str(raw.get("numerical_tolerance", raw.get("tolerance")))
        if tol is not None:
            out["numerical_tolerance"] = tol
        return out

    if qtype == "true_false":
        opts = raw.get("options")
        truth = None
        if isinstance(opts, list):
            for o in opts:
                if isinstance(o, dict) and _truthy(o.get("is_correct", o.get("correct", False))):
                    truth = str(o.get("text", o.get("option", ""))).strip().lower() == "true"
        if truth is None and answer is not None:
            truth = _truthy(answer)
        if truth is not None:
            out["options"] = [
                {"text": "True", "is_correct": truth},
                {"text": "False", "is_correct": not truth},
            ]
        else:
            out["options"] = []
        return out

    # Option-based (single / multi select).
    options = []
    raw_opts = raw.get("options") or raw.get("choices") or []
    if isinstance(raw_opts, dict):  # {"A": "...", "B": "..."}
        raw_opts = [{"label": k, "text": v} for k, v in raw_opts.items()]
    answers = answer if isinstance(answer, list) else ([answer] if answer is not None else [])
    answers_norm = {str(a).strip().lower() for a in answers}
    for idx, o in enumerate(raw_opts):
        if isinstance(o, dict):
            label = str(o.get("label", o.get("key", chr(65 + idx)))).strip()
            otext = str(o.get("text", o.get("option", o.get("value", "")))).strip()
            correct = o.get("is_correct", o.get("correct", o.get("isCorrect")))
        else:
            label, otext, correct = chr(65 + idx), str(o).strip(), None
        if correct is None:
            correct = otext.lower() in answers_norm or label.lower() in answers_norm
        # Strip "A) " / "B. " prefixes some models add.
        otext = re.sub(r"^[A-Ha-h][\).:]\s+", "", otext)
        if otext:
            options.append({"text": otext, "is_correct": _truthy(correct)})
    out["options"] = options
    return out
