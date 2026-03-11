import pdfplumber
import json

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

# --- Usage ---
# Replace 'your_report.pdf' with your actual file path
file_path = "/home/tgk/Downloads/mayer.pdf" 
try:
    json_output = pdf_tables_to_json(file_path)
    print(json_output)
except Exception as e:
    print(f"Error: {e}")