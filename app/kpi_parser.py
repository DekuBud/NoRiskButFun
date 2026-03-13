import re
import json
from typing import Optional, Dict, Any
import os
import requests

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
    Optimized for Llama 3 on GPU.
    """
    context_text = _build_relevant_context(text)

    # Note the double {{ and }} around the JSON structure
    prompt = get_prompt(context_text)

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
    
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
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
            "year": llm_data.get("year"),
            "profit": llm_data.get("profit"),
            "totalCapital": llm_data.get("totalCapital"),
        }
    except Exception as exc:
        print(f"Extraction Error: {exc}")
        return _empty_res()

def _empty_res():
    ''' returns 
    {
        "company_name": "string",
        "year": integer,
        "turnover": float,
        "ebit": float,
        "depreciation": float,
        "ebitda": float,
        "employees": float,
        "investments": float,
        "profit":float,
        "totalCapital":float
        }'''
    return {"company_name": None, "year": None, "turnover": None, "ebit": None, "depreciation": None, "ebitda": None, "employees": None, "investments": None, "profit": None, "totalCapital": None}

def _build_relevant_context(text: str) -> str:
    """
    Extracts windows of text around financial keywords.
    """
    keywords = [
        "umsatzerlöse", "betriebsergebnis", "personalaufwand", 
        "abschreibungen", "anlagen", "sachanlagen", "immaterielle", 
        "zugänge", "investitionen", "investition","anlagenspiegel", 
        "teur", "t€", "mio", "mrd", "millionen", "milliarden",
        "mitarbeiter", "beschäftigte", "jahresabschluss", "geschäftsjahr","gewinn",
        "bilanzsumme", "summe aktiva", "summe passiva", "gesamtvermögen", "bilanz"

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



def parse_kpis_from_json(tables_json: str, raw_text: str = None) -> Dict[str, Any]:
    try:
        tables = json.loads(tables_json)
    except:
        tables = []

    res = {
        "company_name": None, "year": None, "turnover": None, "ebit": None, 
        "depreciation": None, "ebitda": None, "employees": None, "investments": None, "profit": None, "totalCapital": None
    }

    # STEP 1: Detect Global Multiplier (TEUR check)
    # Older Ziegler reports (2017-2019) are almost always in TEUR
    global_multiplier = 1.0
    if raw_text and any(k in raw_text.lower() for k in ["teur", "t€", "in tausend"]):
        global_multiplier = 1000.0

    for table in tables:
        rows = table.get("rows", [])
        for row in rows:
            row_str = " ".join([str(c) for c in row if c]).lower()
            val = _extract_last_numeric(row)
            
            if val is None:
                continue

            # Apply multiplier to the raw value
            # Note: If it's already a million-scale number (like in 2022), don't multiply
            current_val = val * global_multiplier if val < 1000000 else val

            # Expanded Keywords for older HGB styles
            if any(k in row_str for k in ["umsatzerlöse", "umsatz"]):
                if res["turnover"] is None: res["turnover"] = current_val
            
            elif any(k in row_str for k in ["betriebsergebnis", "ergebnis der gewöhnlichen"]):
                if res["ebit"] is None: res["ebit"] = current_val
            
            elif "abschreibungen" in row_str and "anlagevermögen" in row_str:
                if res["depreciation"] is None: res["depreciation"] = current_val
            
            elif any(k in row_str for k in ["zugänge", "investitionen"]):
                if res["investments"] is None: res["investments"] = current_val

            elif "mitarbeiter" in row_str or "beschäftigte" in row_str:
                if res["employees"] is None: res["employees"] = int(val)

    # STEP 2: Fallback for Year (Fixes the 2017 422 error)
    if res["year"] is None and raw_text:
        year_match = re.search(r"(?im)(?:jahresabschluss|geschäftsjahr).{0,30}\b(20\d{2})\b", raw_text)
        if year_match:
            res["year"] = int(year_match.group(1))

    # Calculate EBITDA
    if res["ebitda"] is None and res["ebit"] and res["depreciation"]:
        res["ebitda"] = res["ebit"] + res["depreciation"]
        
    return res

def _extract_last_numeric(row: list) -> Optional[float]:
    """Handles both 1.234,56 and 4.908 (TEUR) formats."""
    for cell in reversed(row):
        if not cell or cell == "": continue
        
        # Remove dots (thousands separator) and change comma to dot
        s = str(cell).replace(".", "").replace(",", ".")
        # If the string has a dot but only 3 digits after it, it might be 4.908 (TEUR)
        # However, our replace(".") above handles the standard HGB dot separator.
        
        clean = _NUM_CLEAN.sub("", s)
        try:
            print(f"Trying to parse numeric value from '{cell}' -> cleaned: '{clean}'")
            f = float(clean)
            # Ignore years
            if 2010 <= f <= 2030: continue
            return f
        except ValueError:
            print(f"Failed to parse numeric value from '{cell}' (cleaned: '{clean}')")
            continue
    return None