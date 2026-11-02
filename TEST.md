# TEST: loppetaicompat 0.1.0 in game (Nick)

Install (after review): copy `out/loppetaicompat_0.1.0.zip` into Mods next to `petai_v5.1.2.zip` and the LoP zips. Use a creative test world (or a copy). Optional: to allow follow-teleport, set `"AllowTeleport": true` in `ModConfig/petconfig.json` (PetAI global setting, default false). Compat config is `ModConfig/loppetaicompat.json` (AllowRevive false, ApplyPetAIDamageRules true, SyncIntervalMs 3000, FallbackMinGeneration 10).

Log check first: `grep -iE "loppetaicompat|petai|patch.*(fail|not found)|Exception" client-main.log server-main.log`. Expect **no** "Patch ... failed" lines for `loppetaicompat:patches/*` and no exceptions mentioning `EntityBehaviorLoPTameable`. A missing family logs nothing because of `dependsOn`.

| # | Step | Pass if |
|---|---|---|
| T0 | Ownership probe: spawn an adult Tyrannosaurus and set its generation to 10 (`/entity wt ...` or breed up). Try attaching a medallion. | Records whether vanilla claim works. Expected: no claim, because LoP ownable has no groupCode. If it does claim, the compat adopts the medallion owner within 3 s. Either way, note the result. |
| T1 | Look at a wild gen 0 rex. | The info text shows no PetAI lines. Right-click with meat does nothing PetAI-related. `/lopbond` replies "Not domesticated yet... generation 0, needs 10". |
| T2 | Tame through the normal LoP generation route (gen >= 10, adult). Look at it. | Info text shows "Domesticated (LoP): hand-feed it...". |
| T3 | Hold **Ctrl** and right-click it with raw meat in hand. A plain right-click mounts it, because LoP's rideable takes the click first. Fallback: stand within 6 blocks and type `/lopbond`. | One meat is consumed (or none with the command), the chat says "...has bonded with you", and the PetAI profile/naming window opens. If Ctrl+right-click does nothing, record the diet: raw meat must match LoP's `creatureDiet`. |
| T4 | Name it in the PetAI window. | The name tag shows when targeted. The info text shows owner and obedience 100%. |
| T5 | Hold **Ctrl + Shift** and right-click it to open the command wheel. Plain sneak+right-click mounts it, because the rideable ignores Shift and only Ctrl skips it. Commands: Follow, Stay, Sit, Lay, Speak. Walk 20+ blocks away while it follows. Then Stay and walk away. Then Sit, Lay, Speak. | It follows at about 10 blocks and stays put. Sit/Lie/Roar animations play. With AllowTeleport true it teleports when more than 40 blocks away and unable to path. |
| T6 | Ride it after bonding (saddle as LoP requires). | Mounting still works exactly as before. |
| T7 | Night: leave it bonded but uncommanded near its herd. | The LoP sleep cycle still runs (sleep anim, path stops). No twitching between sleep and follow while no command is active. |
| T8 | A second player (or alt) tries to bond or command it. | `/lopbond` says it is bonded to another player, and the command GUI does not open for them. |
| T9 | Wild gen 0 rex falls from 10+ blocks. | It takes fall damage as before (PetAI's fall-damage-off applies only to bonded dinos). |
| T10 | Use PetAI "abandon" in the profile window. | Owner is cleared. The rex is still LoP-domesticated and can be re-bonded by feeding. |
| T11 | Breed two bonded rexes and toggle "reproduction" off for one in the profile window. | Report whether eggs still appear. PetAI's toggle only blocks vanilla `TryGetPregnant`, and LoP egg laying is unverified, so a "still lays eggs" result is expected and is not a regression. |
| T12 | Mosasaur, plesiosaur, pterosaur: bond, then open the commands. | No Follow entry. Stay, Sit and Speak (where present) work. Swimmers stay in water. |

Conflict log lines to watch: `Patch .* loppetaicompat`, `Unknown entity behavior`, `NullReference .* (Tameable|ReceiveCommand|FollowMaster)`, and `AiTask .* not found`.
