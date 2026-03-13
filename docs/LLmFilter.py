import requests
import json
import os
import re
from typing import Optional
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "API_KEY")


# prompt text is stored in docs/prompt.txt.
# here we get that text and replace the {{CONTEXT_TEXT}} placeholder with our surgically extracted context.
def get_prompt(context_text: str) -> str:
    with open('docs/prompt.txt', 'r', encoding='utf-8') as f:
        template = f.read()
    
    # 2. Replace the placeholder with your surgical context
    return template.replace('{{CONTEXT_TEXT}}', context_text)

# this is the main function main.py will call.
# it extracts the relevant context from the raw PDF text and then calls the LLM to parse the KPIs.
def parse_kpis(text: str) -> dict[str, Optional[float | int]]:
    """
    Dynamically extracts the most recent year's data.
    Optimized for Qwen 3 on GPU.
    """
    context_text = _build_relevant_context(text)

    # Note the double {{ and }} around the JSON structure
    prompt = get_prompt(context_text)
    final_prompt = f"\\nothink\n{prompt}"

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "qwen3:8b",
                "prompt": final_prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0,
                    "num_ctx": 6096, 
                    "num_predict": 500,
                },
                "keep_alive": "15m",
            },
            timeout=90,
        )

        if response.status_code != 200:
            return _empty_res()

        # Parse the JSON string from the LLM response
        raw_llm_output = response.json().get("response", "{}")
        llm_data = json.loads(raw_llm_output)
        
        return {
            "name": llm_data.get("company_name"),
            "turnover": llm_data.get("turnover"),
            "ebit": llm_data.get("ebit"),
            "depreciation": llm_data.get("depreciation"),
            "ebitda": llm_data.get("ebitda"),
            "employees": llm_data.get("employees"),
            "investments": llm_data.get("investments"),
            "year": llm_data.get("year") # Added to track which year was found
        }
    except Exception as exc:
        print(f"Extraction Error: {exc}")
        return _empty_res()

def _empty_res():
    return {"turnover": None, "ebit": None, "depreciation": None, "ebitda": None, "employees": None, "investments": None, "year": None}

def _build_relevant_context(text: str) -> str:
    """
    Surgically extracts windows of text around financial keywords.
    """
    keywords = [
        "umsatzerlöse", "betriebsergebnis", "personalaufwand", 
        "abschreibungen", "anlagen", "sachanlagen", "immaterielle", # Added these
        "zugänge", "investitionen", "anlagenspiegel", 
        "teur", "t€", "mio", "mrd", "millionen"
    ]
    
    lines = text.splitlines()
    target_indices = set()
    
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in keywords):
            # Capture the context (1 line before, 4 lines after)
            for j in range(max(0, i-1), min(len(lines), i+5)):
                target_indices.add(j)
    
    sorted_indices = sorted(list(target_indices))
    context_parts = []
    last_idx = -1
    for idx in sorted_indices:
        if last_idx != -1 and idx > last_idx + 1:
            context_parts.append("[...]") 
        context_parts.append(lines[idx])
        last_idx = idx

    return "\n".join(context_parts)[:5500]


def parse_kpis_with_gemini(pdf_path: str):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # We define the config as a plain dictionary to avoid SDK mapping errors
        config = {
            "response_mime_type": "application/json",
            "temperature": 0
        }

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                "Extract the most recent financial KPIs from this PDF. Return ONLY JSON.",
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
            ],
            config=config # Pass the dict directly
        )

        return json.loads(response.text)

    except Exception as e:
        # If the error persists, it might be the 'response_mime_type' key itself.
        # Try changing it to 'response_format': {'type': 'application/json'}
        print(f"Gemini API Error: {e}")
        return {"turnover": None, "ebit": None, "depreciation": None, "ebitda": None, "employees": None, "investments": None}