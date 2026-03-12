import pdfplumber
import json
from kpi_parser import parse_kpis_from_json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from docs.LLmFilter import parse_kpis, parse_kpis_with_gemini

def pdf_tables_to_json(pdf_path):
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Extract tables from the current page
            tables = page.extract_tables()
            
            for table_index, table in enumerate(tables):
                # Convert the raw list of lists into a list of dictionaries
                # This assumes the first row of the table contains the headers
                if len(table) > 1:
                    headers = [str(h).replace('\n', ' ') if h else f"Col_{i}" for i, h in enumerate(table[0])]
                    rows = table[1:]
                    
                    table_data = []
                    for row in rows:
                        # Map headers to row values
                        entry = {headers[i]: (str(row[i]).replace('\n', ' ') if i < len(row) else None) for i in range(len(headers))}
                        table_data.append(entry)
                    
                    all_tables.append({
                        "page": page_num,
                        "table_id": table_index + 1,
                        "data": table_data
                    })

    # Return the final list as a formatted JSON string
    return json.dumps(all_tables, indent=4)


def extract_pdf_text(pdf_path):
    page_texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_texts.append(page.extract_text() or "")
    return "\n".join(page_texts)

# --- Usage ---
# Replace 'your_report.pdf' with your actual file path
file_path = "/home/tgk/Downloads/Weiden i. d. OPf._HRA_2209_11.03.2026-3.pdf"
#output_path = file_path.replace(".pdf", ".json")
try:
    '''json_output = pdf_tables_to_json(file_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_output)
    print(f"Saved to {output_path}")
    print()

    # Test table-based parser
    print("=" * 60)
    print("TABLE-BASED PARSER (parse_kpis_from_json)")
    print("=" * 60)
    kpis_table = parse_kpis_from_json(json_output)
    print("Extracted KPIs:")
    for k, v in kpis_table.items():
        print(f"  {k}: {v}")
    print()'''

    # Test LLM filter parser
    print("=" * 60)
    print("LLM FILTER PARSER (parse_kpis)")
    print("=" * 60)
    raw_text = extract_pdf_text(file_path)
    kpis_llm = parse_kpis(raw_text)
    #kpis_llm = parse_kpis_with_gemini(file_path)
    print("Extracted KPIs:")
    for k, v in kpis_llm.items():
        print(f"  {k}: {v}")
    
except Exception as e:
    print(f"Error: {e}")