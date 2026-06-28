import glob
import re
import urllib.request
import hashlib
import concurrent.futures
import os
import sys

def parse_recipes():
    recipes = {}
    for path in glob.glob('recipes/*.recipe'):
        name = os.path.basename(path).replace('.recipe', '')
        with open(path, 'r') as f:
            content = f.read()
        
        # Get source and hash
        source_match = re.search(r'source\s*=\s*\n\s+(http\S+)\s+([a-f0-9]{64})', content)
        url, expected_hash = source_match.groups() if source_match else (None, None)
        
        # Get depends
        depends = []
        dep_match = re.search(r'depends\s*=([^\n]*(?:\n\s+[^\n]+)*)', content)
        if dep_match:
            depends = [d.strip() for d in dep_match.group(1).split() if d.strip()]
            
        makedepends = []
        mdep_match = re.search(r'makedepends\s*=([^\n]*(?:\n\s+[^\n]+)*)', content)
        if mdep_match:
            makedepends = [d.strip() for d in mdep_match.group(1).split() if d.strip()]
            
        recipes[name] = {
            'url': url,
            'expected_hash': expected_hash,
            'depends': depends,
            'makedepends': makedepends
        }
    return recipes

def check_download(name, info):
    if not info['url']:
        return name, True, "No external source"
    
    url = info['url']
    expected_hash = info['expected_hash']
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
        actual_hash = hashlib.sha256(data).hexdigest()
        
        if actual_hash == expected_hash:
            return name, True, "OK"
        else:
            return name, False, f"Hash mismatch. Expected {expected_hash}, got {actual_hash}"
    except Exception as e:
        return name, False, f"Download failed: {e}"

def check_dependencies(recipes):
    all_packages = set(recipes.keys())
    missing = []
    for name, info in recipes.items():
        for dep in info['depends'] + info['makedepends']:
            if dep not in all_packages:
                missing.append((name, dep))
    return missing

def main():
    print("Parsing recipes...")
    recipes = parse_recipes()
    print(f"Found {len(recipes)} recipes.")
    
    print("\nChecking dependencies...")
    missing_deps = check_dependencies(recipes)
    if missing_deps:
        print("MISSING DEPENDENCIES FOUND:")
        for name, dep in missing_deps:
            print(f"  {name} requires missing package '{dep}'")
    else:
        print("All dependencies are satisfied.")
        
    print("\nVerifying downloads and checksums (this will take a few minutes)...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_download, name, info): name for name, info in recipes.items()}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            name, success, msg = future.result()
            results.append((name, success, msg))
            status = "✅" if success else "❌"
            print(f"[{i+1}/{len(recipes)}] {status} {name}: {msg}")
            sys.stdout.flush()
            
    failed = [r for r in results if not r[1]]
    
    print("\n--- AUDIT SUMMARY ---")
    print(f"Total Packages: {len(recipes)}")
    print(f"Passed: {len(results) - len(failed)}")
    print(f"Failed: {len(failed)}")
    
    with open('audit_results.txt', 'w') as f:
        for name, success, msg in results:
            f.write(f"{name}|{success}|{msg}\n")
        f.write(f"MISSING_DEPS|{missing_deps}\n")

if __name__ == '__main__':
    main()
