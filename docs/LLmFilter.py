import requests
import json
import os
import re
from typing import Optional

def parse_kpis(text: str) -> dict[str, Optional[float | int]]:
    """Sends text to local Ollama API to extract German financial KPIs."""

    context_text = _build_relevant_context(text)

    prompt = f"""
    Du bist ein Finanzanalyst. Extrahiere die folgenden Werte aus dem deutschen Text.
    Gib NUR ein JSON-Objekt zurück.
    Felder:
    - turnover (Umsatzerlöse)
    - ebit (Betriebsergebnis)
    - depreciation (Abschreibungen)
    - ebitda (Falls nicht explizit genannt, berechne es als ebit + depreciation)
    - employees (gesamte Mitarbeiteranzahl)

    Text:
    {context_text}
    """

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    primary_model = os.getenv("OLLAMA_MODEL", "llama3:latest")
    fallback_models_env = os.getenv("OLLAMA_FALLBACK_MODELS", "qwen2.5:3b,phi3:mini")
    timeout_seconds = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
    num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "160"))
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
    model_candidates = [primary_model] + [m.strip() for m in fallback_models_env.split(",") if m.strip()]

    last_error: Optional[str] = None
    for model_name in model_candidates:
        try:
            response = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0,
                        "num_predict": num_predict,
                        "num_ctx": num_ctx,
                    },
                    "keep_alive": "15m",
                },
                timeout=(10, timeout_seconds),
            )

            if response.status_code >= 400:
                response_preview = response.text[:300].replace("\n", " ")
                raise RuntimeError(f"HTTP {response.status_code} for model {model_name}: {response_preview}")

            payload = response.json()
            if payload.get("error"):
                raise RuntimeError(f"Model {model_name} error: {payload['error']}")

            llm_data = json.loads(payload.get("response", "{}"))
            return {
                "turnover": llm_data.get("turnover"),
                "ebit": llm_data.get("ebit"),
                "ebitda": llm_data.get("ebitda"),
                "employees": llm_data.get("employees"),
                "investments": llm_data.get("investments", None),
            }
        except Exception as exc:
            last_error = str(exc)
            print(f"LLM model '{model_name}' failed: {last_error}")

    print(f"LLM Error: all models failed. Last error: {last_error}")
    return {"turnover": None, "ebit": None, "ebitda": None, "employees": None, "investments": None}


def _build_relevant_context(text: str) -> str:
    max_chars = int(os.getenv("LLM_INPUT_CHARS", "2500"))
    keyword_re = re.compile(
        r"(?i)(umsatzerl|ebit|betriebsergebnis|abschreib|mitarbeiter|personal|"
        r"zinsen|aufwendungen|steuern|ergebnis\s+nach\s+steuern|jahresergebnis)"
    )

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    selected: list[str] = []
    for line in lines:
        if keyword_re.search(line):
            selected.append(line)
            if len(selected) >= 120:
                break

    if not selected:
        context_text = text[:max_chars]
    else:
        context_text = "\n".join(selected)
        if len(context_text) > max_chars:
            context_text = context_text[:max_chars]

    return context_text
    