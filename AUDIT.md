# AUDIT: PetAI on Legacy of the Phanerozoic (patched 1.22.7 builds)

Sources: PetAI source `G3rste/petai` @3a788c5 plus installed `petai_v5.1.2.zip`; Wolf Taming source @a596f65; patched `LoP-Tyranno-1.4.2-batch0.zip` (`1.4.2-patched-1.22.7`); `LoP-Behaviors-1.0.0.zip`, decompiled; vanilla 1.22.7 decompiled tree (via csnav and explore-audit). Detail files are in `audit/`: `audit_tyranno.md`, `audit_wolftaming.md`, `audit_ownership.md` and `tyranno_inventory.json`.

## 1. Gate 3: which system owns "tamed"

**Answer: LoP owns it. PetAI only records which player bonded with the dino, and it defers to LoP for everything else.**

Evidence:
- PetAI's owner is `WatchedAttributes["domesticationstatus"]` = {domesticationLevel WILD/TAMING/DOMESTICATED, owner, obedience, progress, multiplyAllowed}. It is set only in `EntityBehaviorTameable.OnInteract`: treat feeding moves WILD to TAMING, then progress >= 1 makes it DOMESTICATED, and a magic bone forces DOMESTICATED (`BehaviorTameable.cs:235-269`). PetAI never reads vanilla `ownable`/`ownedby` (audit_wolftaming Part 2).
- LoP domestication is generational. Tyranno server behaviors: `ownable` (s0, `"enabledByType":{"*-baby-*":false,"*":true}, "minGeneration":10`), `rideable` (s4, minGeneration 10), `pettable` (s18, minGeneration 5), `ropetieable` (s19, minGeneration 8). The rideable, pettable and ropetieable gates are enforced by vanilla minGeneration readers (`EntityBehaviorRideable.cs:154`, `EntityRideableSeat.cs:172`, `EntityBehaviorPettable.cs:25`, `EntityBehaviorRopeTieable.cs:136`).
- Vanilla `EntityBehaviorOwnable` reads only `groupCode` (`EntityBehaviorOwnable.cs:22`) and never reads minGeneration. Per-player ownership is claimed by attaching a medallion (`ItemMedallion.OnAttached` calls `ModSystemEntityOwnership.ClaimOwnership`, `:92-125`), which stores `WatchedAttributes["ownedby"]{uid,name}`. LoP's `ownable` has **no groupCode**, so `Group` is null and the claim is skipped (source read by explore-audit, `ModSystemEntityOwnership.cs:98`; **runtime UNVERIFIED**, see TEST.md T0). Vanilla tamed elk uses `groupCode: "mountableanimal"` (`elk-tamed.json:414`).
- Conclusion: in the current patched LoP, "tame" means generation >= threshold (plus adult). There is no working per-player owner, so the two systems can't double-gate unless PetAI's treat taming stays active.

How PetAI defers (class `loptameable`, a subclass of PetAI's `EntityBehaviorTameable`, in the separate code mod `loppetaicompat`):
1. **LoP gate:** bondable only if the variant's `ownable` resolves `enabled` (falling back to `rideable`) and `generation >= minGeneration` of that same behavior. The threshold is read at runtime from each family's own JSON, never hardcoded. Families without ownable or rideable fall back to config `FallbackMinGeneration` (10).
2. **No second taming system:** the treat list is cleared, so PetAI's WILD to TAMING progress can't start. The magic bone path is not called. There is no obedience grind: a bonded dino is always DOMESTICATED with obedience 1, `disobediencePerDay` is 0, and the 3 s sync re-asserts it.
3. **Bond act (records the owner only):** once LoP says tame, hand-feed one item matching the dino's own `creatureDiet` (`CreatureDiet.Matches`). Fallback: look at it and type `/lopbond`. The PetAI naming GUI then opens (PetAI's own `PetProfileMessage`).
4. **Sync, server, every 3 s:** if not LoP-tame, the dino is reset to WILD with no owner (this undoes a creative magic bone or stale state). If a vanilla medallion owner (`ownedby.uid`) ever exists, it wins. PetAI's "abandon" button clears the bond, and the dino can be re-bonded by feeding.
5. **PetAI side effects limited to bonded dinos:** `AfterInitialized` normally applies `petMaxHpModifier` to every tameable, and `OnEntityReceiveDamage` normally zeroes fall damage for every tameable (`BehaviorTameable.cs:451-469`). Both are overridden so wild LoP dinos are untouched.
6. **Not changed:** generation gates, ownable, rideable, pettable, ropetieable, grow, multiply, eggs and nests. All patches are appends, and no LoP value is modified.

## 2. Gate 4: conflict audit (pilot Tyrannosauridae)

| Item | Finding | Result |
|---|---|---|
| Task id collisions | No LoP aitask has an `id` (31 tasks scanned). PetAI tasks are matched by `command`, not id. | none |
| Behavior code collisions | Tyranno has no `tameable`, `receivecommand` or `nametag`. LoP-Behaviors registers `loprippleeffect`, `lopdepthband`, `lopwaterbodygate`, `lopswimfloat` and tasks `herdalarm`, `surfacetobreathe`, `gastrolith`, `vigilantlook`, `satiationwatch`, `sleepguard`, with no overlap with PetAI codes. | none |
| ConfigLib index sensitivity | Rows target s4 (rideable), c4 (rideable) and s13 (harvestable drops), plus spawnconditions. All compat patches append (`/-`), so existing indices can't shift. Mechanically re-verified: 110 behavior-index rows resolve to the same code before and after patching. | 0 shifts |
| Priorities | LoP max is 2.0 (seekentity, herd stayclosetoentity). followmaster 2.1 runs only while commanded and only when farther than maxDistance 10. stay 2.05 with priorityForCancel 1.85, so LoP meleeattack, getoutofwater and flee (1.9) can interrupt a stay and it resumes after. Sit/lay/speak 2.2 are timed commands, cancellable at 1.85. | by design |
| LoP-Behaviors `sleepguard` | ShouldExecute is always false. It stops the path only while a rest idle (sleep/lie/sit) is active. A follow task replaces the idle in the same slot, so no conflict. A commanded sit/lay is a simplecommand, not an AiTaskIdle, so sleepguard ignores it. | none expected; TEST T5 |
| LoP-Behaviors `vigilantlook` / `herdalarm` | vigilantlook freezes movement while a threat is in range (not present in Tyranno). herdalarm stops idles and starts a flee for same-family members **below tamingGenerations**, so bonded dinos are excluded. Neither reads owner. No Harmony in the DLL. | low |
| PetAI global Harmony | AiTaskStayCloseToEntity.OnNoPath postfix, MultiplyPatch, MortallyWoundable, NameTag GetName and Grow.BecomeAdult status copy are **already active** in Nick's install with LoP (PetAI 5.1.2 is installed). This compat adds none. | pre-existing |
| Interaction order | VERIFIED (explore-audit #4): rideable inherits `EntityBehaviorSeatable.OnInteract`. A body click sets `handled = PreventSubsequent` (`EntityBehaviorSeatable.cs:154,181`) regardless of held item or sneak, and returns early only when **Ctrl** is held (`:131`). The Entity loop breaks on PreventSubsequent (`Entity.cs:1529-1531`). The compat must append (ConfigLib indices), so its behaviors run after rideable. Gestures: **Ctrl+right-click with food** bonds, **Ctrl+Shift+right-click** opens PetAI's command GUI (receivecommand needs Sneak, owner and not WILD; `BehaviorReceiveCommand.cs:81-98`). `/lopbond` (nearest unbonded LoP-tame dino within 6 blocks) is the fallback. | TEST T3/T5 |
| Teleport | `allowTeleport &= PetConfig.AllowTeleport` (`AiTaskFollowMaster.cs:18`). The global PetAI config defaults to false. The compat sets allowTeleport true per task, but Nick must enable it globally. | config |

## 3. Per-family wiring recipe (applied by `tools/gen_family.py`, verified by `tools/verify_family.py`)

For each entity JSON in `assets/<family>/entities/**` that has `taskai` plus `ownable` or `rideable` (eggs, nests, lures and hitches are skipped):
- client and server `behaviors/-`: `nametag` (if absent) `{showtagonlywhentargeted:true}`, then `loptameable {size:"large", disobediencePerDay:0}`, then `receivecommand {availableCommands:[followmaster, stay, plus sit/lay/speak when the shape has the animation; minObedience 0]}`.
- server `behaviors/<taskai>/aitasks/-`:
  - `followmaster` (priority 2.1; animation and speed copied from the family's own Run task; maxDistance 10; searchRange 50; allowTeleport true; teleportAfterRange 40)
  - `stay` (2.05 / cancel 1.85; Walk anim and wander speed; `maxdistance` 6, lowercase as PetAI reads it)
  - `simplecommand` sit/lay/speak (2.2 / cancel 1.85) using LoP's own adult idle animation codes (Sit, Lie, Roar or Call).
- Missing animation for a species: `animationByType` falls back per species (Walk for follow, Idle otherwise).
- Swimmers and flyers (mosasauridae, lopplesiosauria, loppterosauria): followmaster is excluded, because following or teleporting to a land owner would beach a swimmer past LoP's water gates, and flyer ground-pathing was not audited.
- Every op carries `dependsOn:[{modid:<family>}]`, so a family that isn't installed is skipped silently.
