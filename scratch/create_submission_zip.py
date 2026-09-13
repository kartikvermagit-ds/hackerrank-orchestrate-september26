import os
import zipfile
import re

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
zip_path = os.path.join(repo_root, "code.zip")

# List of folders/files to include
include_dirs = ["code", "tests", "evaluation"]
include_files = ["README.md"]

# Exclude patterns
def should_include(rel_path):
    # Normalize slashes to forward slash
    norm_path = rel_path.replace("\\", "/")
    
    # Exclude unwanted paths
    if "__pycache__" in norm_path or norm_path.endswith(".pyc"):
        return False
    if norm_path.startswith("dataset") or norm_path.startswith(".git") or norm_path.startswith("scratch"):
        return False
    if norm_path in ["output.csv", "log.txt", ".env", ".gitignore", "AGENTS.md", "problem_statement.md", "code.zip"]:
        return False
        
    return True

print("Creating code.zip...")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    # 1. Add include_files
    for f in include_files:
        f_path = os.path.join(repo_root, f)
        if os.path.isfile(f_path):
            zipf.write(f_path, arcname=f)
            print(f"Added file: {f}")
            
    # 2. Add include_dirs
    for d in include_dirs:
        d_path = os.path.join(repo_root, d)
        for root, _, files in os.walk(d_path):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_root)
                if should_include(rel_path):
                    # Store in zip using forward slashes
                    arcname = rel_path.replace("\\", "/")
                    zipf.write(full_path, arcname=arcname)
                    print(f"Added: {arcname}")

print(f"\ncode.zip created successfully at: {zip_path}")
zip_size = os.path.getsize(zip_path)
print(f"ZIP Size: {zip_size:,} bytes ({zip_size / 1024:.2f} KB)")

# Verification
print("\n=== VERIFICATION ===")
v1 = os.path.isfile(zip_path)
print(f"1. code.zip exists: {v1}")

v2 = False
entries = []
try:
    with zipfile.ZipFile(zip_path, "r") as z:
        entries = z.namelist()
        v2 = True
except Exception as e:
    print(f"Error opening zip: {e}")
print(f"2. ZIP opens successfully: {v2}")

v3 = any(e.startswith("code/") for e in entries)
print(f"3. code/ is present: {v3}")

v4 = any(e.startswith("tests/") for e in entries)
print(f"4. tests/ is present: {v4}")

v5 = any(e.startswith("evaluation/") for e in entries)
print(f"5. evaluation/ is present: {v5}")

v6 = "README.md" in entries
print(f"6. README.md is present: {v6}")

v7 = not any(e.startswith("dataset/") for e in entries)
print(f"7. dataset/ is NOT present: {v7}")

v8 = "output.csv" not in entries and not any(e.endswith("/output.csv") for e in entries)
print(f"8. output.csv is NOT present: {v8}")

v9 = "log.txt" not in entries and not any(e.endswith("/log.txt") for e in entries)
print(f"9. log.txt is NOT present: {v9}")

v10 = not any(".git" in e for e in entries)
print(f"10. .git/ is NOT present: {v10}")

# Secret scan on zip entries
secret_patterns = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{8,}['\"]"),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}")
]
found_secrets = []
with zipfile.ZipFile(zip_path, "r") as z:
    for name in entries:
        with z.open(name) as f:
            for l_no, line in enumerate(f.readlines(), 1):
                line_str = line.decode("utf-8", errors="ignore")
                for sp in secret_patterns:
                    if sp.search(line_str):
                        found_secrets.append(f"{name}:{l_no}")

v11 = (len(found_secrets) == 0)
print(f"11. No secrets/API keys are included: {v11}")

print(f"12. Report ZIP size: {zip_size:,} bytes ({zip_size / 1024:.2f} KB)")

print("\n13. COMPLETE ZIP FILE LISTING:")
for idx, entry in enumerate(sorted(entries), 1):
    print(f"  {idx:2d}. {entry}")
