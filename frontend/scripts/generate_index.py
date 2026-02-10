import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_FILE = os.path.join(ROOT, "CODEBASE_INDEX.md")

def walk(dir_path, prefix=""):
    entries = sorted(os.listdir(dir_path))
    for i, entry in enumerate(entries):
        path = os.path.join(dir_path, entry)
        connector = "├─ " if i < len(entries) - 1 else "└─ "
        line = f"{prefix}{connector}{entry}\n"
        lines.append(line)
        if os.path.isdir(path):
            extension = "│   " if i < len(entries) - 1 else "    "
            walk(path, prefix + extension)

lines = []
walk(ROOT)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.writelines(lines)
print(f"Index written to {OUTPUT_FILE}")
