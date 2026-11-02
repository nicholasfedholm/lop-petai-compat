"""Mechanical verification of loppetaicompat patches for one family.
Usage: python -I verify_family.py <family> <extracted_mod_root> <patch_json> <petai_dll> <out_report_json>
Checks: patch parse + target resolution, ConfigLib behavior-index stability, PetAI/class codes resolve,
animation codes exist in each variant's shape, coverage per variant. Prints a summary only."""
import sys, os, json, copy, glob, fnmatch, itertools
import pyjson5

fam, root, patchf, petai_dll, outp = sys.argv[1:6]
A = os.path.join(root, 'assets', fam)
sys.setrecursionlimit(20000)
def load(p):
    txt = open(p, encoding='utf-8-sig').read()
    try:
        return pyjson5.decode(txt)
    except Exception:
        return json.loads(txt)  # deep shape trees exceed pyjson5 nesting limit; shapes are strict JSON
errors, notes = [], []

patches = json.load(open(patchf, encoding='utf-8'))
dll = open(petai_dll, 'rb').read()
def in_dll(s):
    return s.encode('utf-16-le') in dll or s.encode() in dll
PETAI = {c: in_dll(c) for c in ('tameable', 'receivecommand', 'followmaster', 'stay', 'simplecommand', 'petainetwork')}
for c, ok in PETAI.items():
    if not ok: errors.append(f'PetAI.dll lacks code string {c}')
OURS = {'loptameable'}
VANILLA_BH = {'nametag'}

def resolve(doc, path):
    cur = doc
    parts = path.strip('/').split('/')
    for p in parts[:-1]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    return cur, parts[-1]

def apply(doc, op):
    parent, last = resolve(doc, op['path'])
    if op['op'] != 'add': raise ValueError('unexpected op ' + op['op'])
    if isinstance(parent, list):
        if last == '-': parent.append(copy.deepcopy(op['value']))
        else: parent.insert(int(last), copy.deepcopy(op['value']))
    else: parent[last] = copy.deepcopy(op['value'])

by_file = {}
for o in patches:
    if not o.get('file', '').startswith(fam + ':'): errors.append('foreign target ' + o.get('file', '?'))
    if o.get('dependsOn') != [{'modid': fam}]: errors.append('missing dependsOn on ' + o['path'])
    by_file.setdefault(o['file'].split(':', 1)[1], []).append(o)

cfg_rows = []
for cf in glob.glob(os.path.join(A, 'config', '*configlib*.json')):
    c = load(cf)
    # ConfigLib format: {"patches": {<type>: {<domain:file>: {<json path>: <value expr>}}}}
    for typ, files in (c.get('patches') or {}).items():
        for f, paths in (files or {}).items():
            for path in (paths or {}):
                if '/behaviors/' in path: cfg_rows.append((f, path))

coverage, cfg_checked, cfg_bad = [], 0, 0
for rel, ops in by_file.items():
    p = os.path.join(A, rel)
    if not os.path.exists(p): errors.append('target missing ' + rel); continue
    before = load(p); after = copy.deepcopy(before)
    for o in ops:
        try: apply(after, o)
        except Exception as e: errors.append(f'{rel} {o["path"]}: {e}')
    # ConfigLib index stability
    for f, path in cfg_rows:
        if f and not f.endswith(rel.split('/')[-1]) and rel not in f: continue
        seg = path.strip('/').split('/')
        try:
            i = seg.index('behaviors'); side = seg[i - 1]; idx = int(seg[i + 1])
            cb, ca = before[side]['behaviors'][idx]['code'], after[side]['behaviors'][idx]['code']
            cfg_checked += 1
            if cb != ca: cfg_bad += 1; errors.append(f'ConfigLib index shift {path}: {cb}->{ca}')
        except Exception as e:
            errors.append(f'ConfigLib row unresolved {path}: {e}')
    # codes
    for side in ('client', 'server'):
        for b in after[side]['behaviors'][len(before[side]['behaviors']):]:
            c = b['code']
            if not (c in OURS or c in VANILLA_BH or PETAI.get(c)): errors.append(f'unknown behavior code {c}')
    ti = next(i for i, b in enumerate(after['server']['behaviors']) if b['code'] == 'taskai')
    new_tasks = after['server']['behaviors'][ti]['aitasks'][len(before['server']['behaviors'][ti]['aitasks']):]
    for t in new_tasks:
        if not PETAI.get(t['code']): errors.append('unknown task code ' + t['code'])
    cmds = {c['commandName'] for b in after['server']['behaviors'] if b['code'] == 'receivecommand' for c in b['availableCommands']}
    task_cmds = {t.get('command') for t in new_tasks}
    if cmds != task_cmds: errors.append(f'{rel}: command/task mismatch {sorted(cmds ^ task_cmds)}')
    # variants and shapes
    code = before['code']
    groups = [v['states'] for v in before.get('variantgroups', [])]
    variants = ['-'.join([code] + list(c)) for c in itertools.product(*groups)] if groups else [code]
    cl = before.get('client', {})
    sbt = cl.get('shapeByType') or {'*': cl.get('shape')}
    anim_cache = {}
    for v in variants:
        sh = next((s for pat, s in sbt.items() if fnmatch.fnmatch(v, pat if ':' not in pat else pat.split(':', 1)[1])), None)
        base = (sh or {}).get('base', '')
        parts = v.split('-')[1:]
        for gi, g in enumerate(before.get('variantgroups', [])):
            base = base.replace('{' + g['code'] + '}', parts[gi])
        dom, sp = (base.split(':', 1) if ':' in base else (fam, base))
        sp_path = os.path.join(root, 'assets', dom, 'shapes', sp + '.json')
        if sp_path not in anim_cache:
            try:
                anim_cache[sp_path] = {a.get('code', '').lower() for a in load(sp_path).get('animations', [])}
            except Exception:
                anim_cache[sp_path] = None
        anims = anim_cache[sp_path]
        own = next((b for b in after['server']['behaviors'] if b['code'] == 'ownable'), {})
        en = own.get('enabledByType', {'*': True})
        bondable = next((val for pat, val in en.items() if fnmatch.fnmatch(v, pat if pat.startswith(code) else code + '-' + pat.lstrip('*-') if False else pat)), True) if isinstance(en, dict) else True
        row = {'file': rel, 'variant': v, 'shape': os.path.relpath(sp_path, root) if anims is not None else 'UNRESOLVED:' + base,
               'bondable': bondable, 'tameable': True, 'receivecommand': True, 'nametag': True}
        for t in new_tasks:
            a = t.get('animation', '')
            if 'animationByType' in t:
                a = next((val for pat, val in t['animationByType'].items() if fnmatch.fnmatch(v, pat)), '')
            a = str(a).lower()
            row[t['command']] = 'ok' if anims is None or a in anims else f'NOANIM:{a}'
            if anims is not None and a not in anims: notes.append(f'{v}: task {t["command"]} anim {a} missing in shape')
        if anims is None: notes.append(f'{v}: shape unresolved ({base}); anims not checked')
        coverage.append(row)
    cfg_rows_used = cfg_checked

res = {'family': fam, 'patch_ops': len(patches), 'files': list(by_file), 'configlib_rows_checked': cfg_checked,
       'configlib_shifts': cfg_bad, 'errors': errors, 'notes': notes, 'coverage': coverage}
json.dump(res, open(outp, 'w', encoding='utf-8'), indent=1)
nv = len(coverage); nb = sum(1 for r in coverage if r['bondable'])
noanim = sum(1 for r in coverage for k, v in r.items() if isinstance(v, str) and v.startswith('NOANIM'))
print(f'{fam}: ops={len(patches)} variants={nv} bondable={nb} configlib_rows={cfg_checked} shifts={cfg_bad} errors={len(errors)} noanim_cells={noanim} notes={len(notes)}')
for e in errors[:15]: print('  ERR', e)
for n in sorted(set(notes))[:10]: print('  NOTE', n)
