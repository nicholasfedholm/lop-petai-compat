"""Package the built mod into out/loppetaicompat_<version>.zip and verify it.
Usage: python -I package.py <build_dir> <out_dir>
Includes: modinfo.json, LoPPetAICompat.dll, assets/** (no pdb/deps). Prints file list, size, sha256, and checks."""
import sys, os, json, zipfile, hashlib
import pyjson5

build, out = sys.argv[1:3]
mi = json.load(open(os.path.join(build, 'modinfo.json'), encoding='utf-8-sig'))
os.makedirs(out, exist_ok=True)
zp = os.path.join(out, f"loppetaicompat_{mi['version']}.zip")
files = ['modinfo.json', 'LoPPetAICompat.dll']
for dp, _, fs in os.walk(os.path.join(build, 'assets')):
    for f in fs:
        files.append(os.path.relpath(os.path.join(dp, f), build).replace('\\', '/'))
if os.path.exists(zp): os.remove(zp)
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(files):
        z.write(os.path.join(build, f), f)
with zipfile.ZipFile(zp) as z:
    bad = z.testzip()
    names = z.namelist()
    jerr = []
    for n in names:
        if n.endswith('.json'):
            try: pyjson5.decode(z.read(n).decode('utf-8-sig'))
            except Exception as e: jerr.append(f'{n}: {e}')
    sizes = {i.filename: i.file_size for i in z.infolist()}
h = hashlib.sha256(open(zp, 'rb').read()).hexdigest()
print(f'zip={zp}\nsize={os.path.getsize(zp)} sha256={h}\ntestzip={bad or "OK"} entries={len(names)} json_errors={len(jerr)}')
for n in names: print(f'  {sizes[n]:>8} {n}')
for e in jerr: print('  JSONERR', e)
