import os
import re
import hashlib
import subprocess
from pathlib import Path
import tempfile
import sys

def compute_hash(url):
    print(f"Downloading {url}...")
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            
        subprocess.run(
            ['curl', '-f', '-L', '-m', '600', '-A', 'Mozilla/5.0', '-s', '-o', tmp_path, url],
            check=True
        )
        
        if os.path.getsize(tmp_path) < 1024:
            os.unlink(tmp_path)
            print(f"FAILED {url}: File too small")
            return None
            
        sha256 = hashlib.sha256()
        with open(tmp_path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
                
        os.unlink(tmp_path)
        return sha256.hexdigest()
    except Exception as e:
        print(f"FAILED {url}: {e}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return None

def main():
    failed_names = [
        "binutils", "groff", "linux", "zsh", "nmap", "tar", "libiconv",
        "autoconf", "coreutils", "diffutils", "bash", "gdbm", "patch", "gmp",
        "sed", "findutils", "man-db", "readline", "gdb", "libidn2",
        "libunistring", "valgrind", "wget", "which", "texinfo",
        "zlib", "wireless_tools"
    ]
    
    recipe_dir = Path('recipes')
    pattern = re.compile(r'^(\s+)(https?://\S+)\s+([a-fA-F0-9]{32,})(.*)$')
    
    for name in failed_names:
        filepath = recipe_dir / f"{name}.recipe"
        if not filepath.exists():
            print(f"NOT FOUND: {filepath}")
            continue
            
        content = filepath.read_text(encoding='utf-8')
        lines = content.split('\n')
        new_lines = []
        changed = False
        
        for line in lines:
            match = pattern.match(line)
            if match:
                indent, url, old_hash, rest = match.groups()
                
                # Fetch the hash
                new_hash = compute_hash(url)
                if new_hash and old_hash != new_hash:
                    new_lines.append(f"{indent}{url}    {new_hash}{rest}")
                    changed = True
                    print(f"Updated {filepath.name}: {new_hash}")
                else:
                    new_lines.append(line)
                    if new_hash:
                        print(f"Hash unchanged for {filepath.name}")
            else:
                new_lines.append(line)
                
        if changed:
            filepath.write_text('\n'.join(new_lines), encoding='utf-8')

if __name__ == "__main__":
    main()
