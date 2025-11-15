# encode.py
import base64
from pathlib import Path

# ... soma data ya PDF ...
pdf_path = Path("AZANIA.pdf")
pdf_bytes = pdf_path.read_bytes()
base64_string = base64.b64encode(pdf_bytes).decode("utf-8")

# Gawanya string katika vipande viwili (unaweza kuongeza zaidi)
half_length = len(base64_string) // 2 
part1 = base64_string[:half_length]
part2 = base64_string[half_length:]

print("---------------------------------")
print("NAKILI PART 1 KWENYE AZANIA_PDF_DATA_1")
print("---------------------------------")
print(part1)

# print("\n---------------------------------")
# print("NAKILI PART 2 KWENYE AZANIA_PDF_DATA_2")
# print("---------------------------------")
# print(part2)