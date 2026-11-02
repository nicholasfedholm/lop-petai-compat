# LoP PetAI Compat (loppetaicompat)

An optional Vintage Story 1.22.7 code mod that gives Legacy of the Phanerozoic dinosaurs a PetAI layer (PetAI 5.1.2 by G3rste) without replacing LoP's generational domestication.

- **LoP decides when a dino is tame**: the variant's `ownable` is enabled and `generation >= minGeneration`, read from each family's own JSON at runtime. PetAI's treat-taming, magic bone and obedience decay are disabled for these entities.
- **Bond**: Ctrl + right-click a LoP-domesticated adult with its own food (`creatureDiet`), or stand within 6 blocks and type `/lopbond`. The PetAI naming window opens.
- **Commands**: Ctrl + Shift + right-click opens PetAI's command wheel (follow, stay, sit, lay, speak where the shape has the animation). Plain right-click still mounts. Follow-teleport needs `AllowTeleport: true` in PetAI's `petconfig.json`.
- **Swimmers and pterosaurs** have no follow command.
- All patches are appends with `dependsOn`, so families you don't have installed are skipped, and LoP ConfigLib behavior indices never shift.

Config: `ModConfig/loppetaicompat.json` (`AllowRevive` false, `ApplyPetAIDamageRules` true, `SyncIntervalMs` 3000, `FallbackMinGeneration` 10).

Build: `dotnet build src/LoPPetAICompat/LoPPetAICompat.csproj -c Release -p:VINTAGE_STORY=<game dir> -p:PETAI_DLL=<path to PetAI.dll from petai_v5.1.2.zip>`, then package with `python tools/package.py src/LoPPetAICompat/bin/Release/Mods/mod out`.
Regenerate patches: `python tools/rollout.py <Mods dir> <tmp dir> src/LoPPetAICompat/assets/loppetaicompat/patches audit/reports <PetAI.dll> <family modids...>` (run twice so the per-species animation fallbacks apply).

See AUDIT.md for the design evidence and TEST.md for the in-game test plan.
