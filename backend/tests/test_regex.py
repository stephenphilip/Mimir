import re

prompt = "[Attached file: Stephen_BA_Resume (2).pdf (54.6 KB, type=pdf). File is attached in the UI; use its name if generating related outputs.]"
pattern = r"\[Attached file:\s*(.+?)\s*\(\d+(?:\.\d+)?\s*(?:B|KB|MB|GB),\s*type=(.+?)\)\.\s*File is attached in the UI;\s*use its name if generating related outputs\.\]"

print("Regex Matches:")
print(re.findall(pattern, prompt))
