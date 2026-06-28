import os
import re
import hashlib
import subprocess
from pathlib import Path
import tempfile

def compute_hash(url):
    print(f"Downloading {url}...")
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            
        subprocess.run(
            ['curl', '-f', '-L', '-m', '120', '-A', 'Mozilla/5.0', '-s', '-o', tmp_path, url],
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
    failed_urls = []
    with open('fix.log', 'r') as f:
        for line in f:
            if line.startswith('FAILED '):
                # FAILED https://ftp.gnu.org/...: CURL ERROR 28
                m = re.match(r'FAILED (https?://\S+):', line)
                if m:
                    url = m.group(1)
                    if url not in failed_urls:
                        failed_urls.append(url)
                        
    recipe_dir = Path('recipes')
    files = list(recipe_dir.rglob('*.recipe')) + list(recipe_dir.rglob('*.txrecipe'))
    
    # Map URLs to files
    url_to_file = {}
    pattern = re.compile(r'^(\s+)(https?://\S+)\s+([a-fA-F0-9]{32,})(.*)$')
    for filepath in files:
        content = filepath.read_text(encoding='utf-8')
        for line in content.split('\n'):
            match = pattern.match(line)
            if match:
                url_to_file[match.group(2)] = filepath

    for url in failed_urls:
        if url not in url_to_file:
            print(f"URL not found in recipes: {url}")
            continue
            
        filepath = url_to_file[url]
        # Modify the URL to use ftpmirror for GNU
        fetch_url = url.replace('ftp.gnu.org/gnu/', 'ftpmirror.gnu.org/')
        
        new_hash = compute_hash(fetch_url)
        if new_hash:
            content = filepath.read_text(encoding='utf-8')
            lines = content.split('\n')
            new_lines = []
            changed = False
            for line in lines:
                match = pattern.match(line)
                if match and match.group(2) == url:
                    indent, _, old_hash, rest = match.groups()
                    if old_hash != new_hash:
                        new_lines.append(f"{indent}{url}    {new_hash}{rest}")
                        changed = True
                        print(f"Updated {filepath.name}: {new_hash}")
                    else:
                        new_lines.append(line)
                        print(f"Hash unchanged for {filepath.name}")
                else:
                    new_lines.append(line)
            if changed:
                filepath.write_text('\n'.join(new_lines), encoding='utf-8')

if __name__ == "__main__":
    main()
