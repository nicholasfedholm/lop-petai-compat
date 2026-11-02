"""Phase 2 rollout: for each family modid, locate its zip in the Mods folder (READ-ONLY), extract entities/shapes/config
to a temp dir, run gen_family.py + verify_family.py. One line per family.
Usage: python -I rollout.py <mods_dir> <tmp_dir> <patch_dir> <report_dir> <petai_dll> fam1 fam2 ..."""
import sys, os, json, zipfile, subprocess

mods, tmp, patchdir, repdir, petai = sys.argv[1:6]
fams = sys.argv[6:]
here = os.path.dirname(os.path.abspath(__file__))
index = {}
for f in os.listdir(mods):
    if not f.lower().endswith('.zip'): continue
    try:
        with zipfile.ZipFile(os.path.join(mods, f)) as z:
            n = next((x for x in z.namelist() if x.lower() == 'modinfo.json'), None)
            if not n: continue
            import pyjson5
            mi = pyjson5.decode(z.read(n).decode('utf-8-sig'))
            index[str(mi.get('modid') or mi.get('modID') or '').lower()] = (f, mi.get('version'))
    except Exception:
        pass
summary = []
for fam in fams:
    if fam not in index:
        print(f'{fam}: BLOCKED zip not found in Mods'); summary.append({'family': fam, 'status': 'BLOCKED', 'reason': 'zip not found'}); continue
    zf, ver = index[fam]
    dst = os.path.join(tmp, fam)
    with zipfile.ZipFile(os.path.join(mods, zf)) as z:
        for n in z.namelist():
            low = n.lower()
            if n.endswith('/'): continue
            if any(f'/{k}/' in low for k in ('entities', 'shapes', 'config')) and low.endswith('.json') and '..' not in n:
                z.extract(n, dst)
    # no follow/teleport: swimmers (beaching past LoP water gates) and flyers (ground pathing, not audited)
    extra_args = ['--aquatic'] if fam in ('mosasauridae', 'lopichthyosauria', 'lopplesiosauria', 'loppterosauria') else []
    prev = os.path.join(repdir, f'verify_{fam}.json')
    if os.path.exists(prev): extra_args.append('--prev=' + prev)
    g = subprocess.run([sys.executable, '-I', os.path.join(here, 'gen_family.py'), fam, dst, patchdir, os.path.join(repdir, f'{fam}.json')] + extra_args, capture_output=True, text=True)
    v = subprocess.run([sys.executable, '-I', os.path.join(here, 'verify_family.py'), fam, dst, os.path.join(patchdir, f'{fam}.json'), petai, os.path.join(repdir, f'verify_{fam}.json')], capture_output=True, text=True)
    gl = (g.stdout.strip().splitlines() or [g.stderr.strip()[-200:]])
    vl = (v.stdout.strip().splitlines() or [v.stderr.strip()[-300:]])
    print(f'{fam} [{zf} v{ver}]\n  GEN {gl[0]}\n  VER {vl[0]}')
    for extra in gl[1:] + vl[1:]:
        if 'skip' in extra or 'ERR' in extra or 'NOTE' in extra or 'cmds' in extra: print('   ', extra.strip()[:220])
    summary.append({'family': fam, 'zip': zf, 'version': ver, 'gen': gl[0], 'verify': vl[0]})
json.dump(summary, open(os.path.join(repdir, 'rollout_summary.json'), 'w'), indent=1)
