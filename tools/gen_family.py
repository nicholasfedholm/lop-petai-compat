"""Generate loppetaicompat patches for one LoP family from its extracted (read-only) asset tree.
Usage: python -I gen_family.py <family_modid> <extracted_mod_root> <out_patch_dir> <report_json>
Append-only patches (/-) so existing behavior indices (ConfigLib) never shift. Prints a summary only."""
import sys, os, json, copy, glob
import pyjson5

fam, root, outdir, report = sys.argv[1:5]
AQUATIC = '--aquatic' in sys.argv[5:]
PREV = {}
for a in sys.argv[5:]:
    if a.startswith('--prev='):
        try:
            for r in json.load(open(a[7:], encoding='utf-8'))['coverage']:
                PREV.setdefault(r['file'], []).append(r)
        except Exception:
            PREV = {}
ent_dir = os.path.join(root, 'assets', fam, 'entities')
rows, patches, skipped = [], [], []

def load(p):
    return pyjson5.decode(open(p, encoding='utf-8-sig').read())

def find(bhs, code):
    for i, b in enumerate(bhs):
        if b.get('code') == code:
            return i, b
    return None, None

def anim_pick(tasks, words):
    for t in tasks:
        if t.get('code') != 'idle':
            continue
        en = t.get('enabledByType')
        if isinstance(en, dict) and en.get('*') is False:
            continue  # baby-only or variant-only idle; prefer one enabled for adults
        a = t.get('animation')
        if isinstance(a, str) and a.lower() in words:
            return a
    return None

def speed_keys(t):
    return {k: copy.deepcopy(v) for k, v in t.items() if k.lower() in ('movespeed', 'movespeedbytype', 'animationspeed', 'animationspeedbytype')}

for p in sorted(glob.glob(os.path.join(ent_dir, '**', '*.json'), recursive=True)):
    rel = os.path.relpath(p, os.path.join(root, 'assets', fam)).replace('\\', '/')
    d = load(p)
    srv = d.get('server', {}).get('behaviors', [])
    cli = d.get('client', {}).get('behaviors', [])
    oi, own = find(srv, 'ownable')
    ri, ride = find(srv, 'rideable')
    ti, tai = find(srv, 'taskai')
    if tai is None or (own is None and ride is None):
        skipped.append((rel, 'no taskai or no ownable/rideable (not a tameable creature)'))
        continue
    if any(b.get('code') in ('tameable', 'loptameable', 'receivecommand') for b in srv + cli):
        skipped.append((rel, 'already has PetAI behaviors'))
        continue
    tasks = tai.get('aitasks', [])
    sit = anim_pick(tasks, {'sit'})
    lie = anim_pick(tasks, {'lie', 'lay', 'rest'})
    speak = anim_pick(tasks, {'roar', 'call', 'howl', 'bellow', 'growl', 'honk', 'display'})
    run = next((t for t in tasks if str(t.get('animation', '')).lower() == 'run'), None)
    walk = next((t for t in tasks if t.get('code') == 'wander'), None)
    follow_anim = run.get('animation') if run else (walk.get('animation') if walk else 'Walk')
    follow_speed = speed_keys(run or walk or {}) or {'movespeed': 0.03}
    stay_speed = speed_keys(walk or {}) or {'movespeed': 0.01}

    cmds = [{'commandName': 'followmaster', 'commandType': 'COMPLEX', 'minObedience': 0},
            {'commandName': 'stay', 'commandType': 'COMPLEX', 'minObedience': 0}]
    new_tasks = [
        dict({'code': 'followmaster', 'command': 'followmaster', 'priority': 2.1, 'animation': follow_anim,
              'maxDistance': 10, 'searchRange': 50, 'allowTeleport': True, 'teleportAfterRange': 40}, **follow_speed),
        dict({'code': 'stay', 'command': 'stay', 'priority': 2.05, 'priorityForCancel': 1.85,
              'animation': (walk or {}).get('animation', 'Walk'), 'maxdistance': 6, 'searchRange': 50}, **stay_speed),
    ]
    for name, anim, dur in (('sit', sit, (10000, 30000)), ('lay', lie, (30000, 120000)), ('speak', speak, (3000, 3000))):
        if anim:
            cmds.append({'commandName': name, 'commandType': 'SIMPLE', 'minObedience': 0})
            new_tasks.append({'code': 'simplecommand', 'command': name, 'priority': 2.2, 'priorityForCancel': 1.85,
                              'minduration': dur[0], 'maxduration': dur[1], 'animation': anim})

    if AQUATIC:
        # follow/teleport-to-owner would drag or teleport a swimmer onto land past LoP's water gates: excluded
        cmds = [c for c in cmds if c['commandName'] != 'followmaster']
        new_tasks = [t for t in new_tasks if t['command'] != 'followmaster']
    # per-species animation fallback where the shape lacks the chosen animation (from a previous verify report)
    for t in new_tasks:
        missing = sorted({r['variant'].split('-')[1] for r in PREV.get(rel, []) if str(r.get(t['command'], '')).startswith('NOANIM')})
        if missing:
            fb = (walk or {}).get('animation', 'Walk') if t['command'] == 'followmaster' else 'Idle'
            abt = {f'*-{sp}-*': fb for sp in missing}
            abt['*'] = t.pop('animation')
            t['animationByType'] = abt
    file_ref = f'{fam}:{rel}'
    tame = {'code': 'loptameable', 'size': 'large', 'disobediencePerDay': 0}
    recv = {'code': 'receivecommand', 'availableCommands': cmds}
    ntag = {'code': 'nametag', 'showtagonlywhentargeted': True}
    has_tag_s = find(srv, 'nametag')[0] is not None
    has_tag_c = find(cli, 'nametag')[0] is not None
    ops = []
    for side, has_tag in (('client', has_tag_c), ('server', has_tag_s)):
        if not has_tag:
            ops.append({'op': 'add', 'path': f'/{side}/behaviors/-', 'value': ntag})
        ops.append({'op': 'add', 'path': f'/{side}/behaviors/-', 'value': tame})
        ops.append({'op': 'add', 'path': f'/{side}/behaviors/-', 'value': recv})
    for t in new_tasks:
        ops.append({'op': 'add', 'path': f'/server/behaviors/{ti}/aitasks/-', 'value': t})
    for o in ops:
        o['file'] = file_ref
        o['side'] = 'Server' if o['path'].startswith('/server') else 'Universal'
        o['dependsOn'] = [{'modid': fam}]
    patches.extend(ops)
    vg = [(v['code'], v.get('states', [])) for v in d.get('variantgroups', [])]
    rows.append({'file': rel, 'variantgroups': vg, 'taskai_index': ti, 'ownable_minGen': (own or {}).get('minGeneration'),
                 'rideable_minGen': (ride or {}).get('minGeneration'), 'ownable_enabledByType': (own or {}).get('enabledByType'),
                 'client_len_before': len(cli), 'server_len_before': len(srv), 'tasks_before': len(tasks),
                 'commands': [c['commandName'] for c in cmds], 'anims': {'sit': sit, 'lay': lie, 'speak': speak, 'follow': follow_anim},
                 'ops': len(ops)})

os.makedirs(outdir, exist_ok=True)
outp = os.path.join(outdir, f'{fam}.json')
json.dump(patches, open(outp, 'w', encoding='utf-8'), indent=2)
json.dump({'family': fam, 'rows': rows, 'skipped': skipped}, open(report, 'w', encoding='utf-8'), indent=2)
print(f'{fam}: entities wired={len(rows)} skipped={len(skipped)} ops={len(patches)} -> {outp}')
for r in rows:
    print(' ', r['file'], 'taskai@', r['taskai_index'], 'gen own/ride', r['ownable_minGen'], r['rideable_minGen'], 'cmds', r['commands'], 'anims', r['anims'])
for s in skipped:
    print('  skip', s[0], '-', s[1])
