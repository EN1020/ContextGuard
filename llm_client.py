import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI


@dataclass(frozen=True)
class LLMConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_retries: int = 3
    base_backoff_sec: float = 0.8
    timeout_sec: float = 20.0  # hard timeout for each attempt


class LLMCallError(RuntimeError):
    pass


def _try_extract_json(text: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Best-effort JSON extraction:
    - First try full parse.
    - Then try to extract the first {...} block.
    """
    s = (text or "").strip()
    if not s:
        return False, None

    # 1) direct parse
    try:
        return True, json.loads(s)
    except Exception:
        pass

    # 2) extract first JSON object block
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = s[start : end + 1]
        try:
            return True, json.loads(candidate)
        except Exception:
            return False, None

    return False, None


def call_analyzer_llm(
    client: OpenAI,
    cfg: LLMConfig,
    system_prompt: str,
    user_content: str,
    *,
    logger=print,
) -> Dict[str, Any]:
    """
    Calls LLM with retry/backoff + timeout, returns parsed JSON dict.
    Raises LLMCallError if all attempts fail to produce JSON.
    """
    last_err: Optional[Exception] = None

    for attempt in range(1, cfg.max_retries + 1):
        try:
            logger(f"[LLM] attempt={attempt}/{cfg.max_retries} model={cfg.model}")

            resp = client.chat.completions.create(
                model=cfg.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=cfg.temperature,
                timeout=cfg.timeout_sec,  # OpenAI python SDK supports request timeout
            )

            raw = (resp.choices[0].message.content or "").strip()
            ok, parsed = _try_extract_json(raw)
            if ok and isinstance(parsed, dict):
                return parsed

            raise ValueError("Model response is not valid JSON.")

        except Exception as e:
            last_err = e
            logger(f"[LLM] error attempt={attempt}: {type(e).__name__}: {e}")

            if attempt < cfg.max_retries:
                sleep_s = cfg.base_backoff_sec * (2 ** (attempt - 1))
                logger(f"[LLM] backoff {sleep_s:.1f}s")
                time.sleep(sleep_s)

    raise LLMCallError(f"All retries failed. last_error={type(last_err).__name__}: {last_err}")
