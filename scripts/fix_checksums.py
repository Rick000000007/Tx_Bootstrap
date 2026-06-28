import os
import re
import hashlib
import subprocess
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor

def compute_hash(url):
    print(f"Downloading {url}...")
    tmp_path = ""
    try:
        # Create a temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            
        subprocess.run(
            ['curl', '-f', '-L', '-m', '60', '-A', 'Mozilla/5.0', '-s', '-o', tmp_path, url],
            check=True
        )
        
        # Verify size > 1KB to ensure it's not an empty/error page
        if os.path.getsize(tmp_path) < 1024:
            os.unlink(tmp_path)
            print(f"FAILED {url}: File too small")
            return None
            
        # Hash it
        sha256 = hashlib.sha256()
        with open(tmp_path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
                
        os.unlink(tmp_path)
        return sha256.hexdigest()
    except subprocess.CalledProcessError as e:
        print(f"FAILED {url}: CURL ERROR {e.returncode}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    except Exception as e:
        print(f"FAILED {url}: {e}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return None

def process_file(filepath):
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')
    changed = False
    
    # Matches: leading spaces + URL + spaces + hex string (any length) + trailing stuff
    pattern = re.compile(r'^(\s+)(https?://\S+)\s+([a-fA-F0-9]{32,})(.*)$')
    
    new_lines = []
    for line in lines:
        match = pattern.match(line)
        if match:
            indent, url, old_hash, rest = match.groups()
            new_hash = compute_hash(url)
            if new_hash:
                if new_hash != old_hash:
                    new_line = f"{indent}{url}    {new_hash}{rest}"
                    new_lines.append(new_line)
                    changed = True
                    print(f"Updated {filepath.name}: {new_hash}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    if changed:
        filepath.write_text('\n'.join(new_lines), encoding='utf-8')

def main():
    recipe_dir = Path('recipes')
    files = list(recipe_dir.rglob('*.recipe')) + list(recipe_dir.rglob('*.txrecipe'))
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(process_file, files)
        
if __name__ == "__main__":
    main()
