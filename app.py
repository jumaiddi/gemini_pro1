import base64
from pathlib import Path

# Soma data ya binary ya faili lako la PDF
pdf_path = Path("AZANIA.pdf")
pdf_bytes = pdf_path.read_bytes()

# Badilisha kuwa Base64 string
base64_string = base64.b64encode(pdf_bytes).decode("utf-8")

print("---------------------------------")
print("COPY THIS ENTIRE STRING TO secrets.toml")
print("---------------------------------")
print(base64_string)