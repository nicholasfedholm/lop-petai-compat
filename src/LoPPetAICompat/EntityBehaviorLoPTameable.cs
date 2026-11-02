using System;
using System.Text;
using PetAI;
using Vintagestory.API.Client;
using Vintagestory.API.Common;
using Vintagestory.API.Common.Entities;
using Vintagestory.API.Config;
using Vintagestory.API.Datastructures;
using Vintagestory.API.MathTools;
using Vintagestory.API.Server;
using Vintagestory.GameContent;

namespace LoPPetAICompat
{
    /// <summary>
    /// PetAI tameable that defers to Legacy of the Phanerozoic's generational domestication.
    /// LoP decides "tame": alive, ownable enabled for this variant, generation >= ownable minGeneration.
    /// PetAI only records WHICH player bonded (domesticationstatus owner), always DOMESTICATED with obedience 1.
    /// PetAI's own treat taming, magic bone and (by default) revive are disabled for LoP entities.
    /// </summary>
    public class EntityBehaviorLoPTameable : EntityBehaviorTameable
    {
        int bondMinGeneration;
        bool bondableVariant;
        CreatureDiet diet;
        long syncListenerId;

        static LoPPetAICompatConfig Cfg => LoPPetAICompatModSystem.Config;

        public EntityBehaviorLoPTameable(Entity entity) : base(entity) { }

        public override string PropertyName() => "tameable";

        public int BondMinGeneration => bondMinGeneration;

        public override void Initialize(EntityProperties properties, JsonObject attributes)
        {
            base.Initialize(properties, attributes);
            treatList.Clear(); // no PetAI treat taming on LoP dinos

            ResolveLoPGate(properties);
            try { diet = properties.Attributes?["creatureDiet"]?.AsObject<CreatureDiet>(); }
            catch (Exception) { diet = null; }

            if (entity.Api.Side == EnumAppSide.Server)
            {
                entity.Api.Event.EnqueueMainThreadTask(() =>
                    syncListenerId = entity.World.RegisterGameTickListener(Sync, Math.Max(500, Cfg.SyncIntervalMs)),
                    "loppetaicompat sync listener");
            }
        }

        void ResolveLoPGate(EntityProperties properties)
        {
            bondMinGeneration = -1;
            bondableVariant = false;
            JsonObject[] jsons = properties.Server?.BehaviorsAsJsonObj ?? properties.Client?.BehaviorsAsJsonObj;
            if (jsons != null)
            {
                foreach (var code in new[] { "ownable", "rideable" })
                {
                    foreach (var bh in jsons)
                    {
                        if (bh?["code"]?.AsString() != code) continue;
                        bondableVariant = bh["enabled"].AsBool(true);
                        bondMinGeneration = bh["minGeneration"].AsInt(-1);
                        break;
                    }
                    if (bondMinGeneration >= 0) break;
                }
            }
            if (bondMinGeneration < 0) bondMinGeneration = Cfg.FallbackMinGeneration;
        }

        int Gen => entity.WatchedAttributes.GetInt("generation", 0);

        string MedallionOwnerUid => entity.WatchedAttributes.GetTreeAttribute("ownedby")?.GetString("uid");

        /// <summary>LoP's own verdict: is this dino domesticated enough to be someone's?</summary>
        public bool IsLoPTame => bondableVariant && Gen >= bondMinGeneration;

        public bool IsBonded => DomesticationLevel == DomesticationLevel.DOMESTICATED && !string.IsNullOrEmpty(OwnerId);

        void Sync(float dt)
        {
            if (!entity.Alive) return; // keep owner through death (PetAI death message, optional revive)
            string medUid = MedallionOwnerUid;

            if (!IsLoPTame)
            {
                if (DomesticationLevel != DomesticationLevel.WILD || !string.IsNullOrEmpty(OwnerId)) Unbond();
                return;
            }
            if (!string.IsNullOrEmpty(medUid) && medUid != OwnerId) { Bond(medUid, false); return; }
            if (!string.IsNullOrEmpty(OwnerId) && DomesticationLevel != DomesticationLevel.DOMESTICATED) { Bond(OwnerId, false); return; }
            if (string.IsNullOrEmpty(OwnerId) && DomesticationLevel != DomesticationLevel.WILD) { Unbond(); return; }
            if (DomesticationLevel == DomesticationLevel.DOMESTICATED && Obedience < 1f) Obedience = 1f;
        }

        void Bond(string uid, bool openProfile)
        {
            DomesticationLevel = DomesticationLevel.DOMESTICATED;
            OwnerId = uid;
            Obedience = 1f;
            ApplyHpModifier(true);
            if (entity.Api is ICoreServerAPI sapi && entity.World.PlayerByUid(uid) is IServerPlayer splr)
            {
                splr.SendMessage(GlobalConstants.GeneralChatGroup, Lang.Get("loppetaicompat:message-bonded", entity.GetName()), EnumChatType.Notification);
                if (openProfile)
                {
                    try
                    {
                        sapi.Network.GetChannel("petainetwork").SendPacket(new PetProfileMessage { targetEntityUID = entity.EntityId, oldEntityUID = entity.EntityId }, splr);
                    }
                    catch (Exception e) { sapi.Logger.Warning("[loppetaicompat] could not open PetAI profile GUI: {0}", e.Message); }
                }
            }
        }

        void Unbond()
        {
            DomesticationLevel = DomesticationLevel.WILD;
            OwnerId = null;
            ApplyHpModifier(false);
        }

        void ApplyHpModifier(bool bonded)
        {
            var hp = entity.GetBehavior<EntityBehaviorHealth>();
            if (hp == null) return;
            float mod = bonded && Cfg.ApplyPetAIDamageRules ? (PetConfig.Current?.Difficulty?.petMaxHpModifier ?? 0f) : 0f;
            hp.SetMaxHealthModifiers("petconfig", mod);
        }

        public override void AfterInitialized(bool onFirstSpawn)
        {
            // base applies petMaxHpModifier to every tameable; restrict it to bonded dinos
            ApplyHpModifier(IsBonded);
        }

        /// <summary>Hand-feed one item of the dino's own diet to bond, once LoP considers it tame.</summary>
        public override void OnInteract(EntityAgent byEntity, ItemSlot itemslot, Vec3d hitPosition, EnumInteractMode mode, ref EnumHandling handled)
        {
            if (byEntity is not EntityPlayer player || mode != EnumInteractMode.Interact) return;

            if (!entity.Alive)
            {
                if (Cfg.AllowRevive && IsBonded && OwnerId == player.PlayerUID)
                {
                    base.OnInteract(byEntity, itemslot, hitPosition, mode, ref handled);
                }
                return;
            }

            if (itemslot?.Itemstack == null || !IsLoPTame || !string.IsNullOrEmpty(OwnerId)) return;
            string medUid = MedallionOwnerUid;
            if (!string.IsNullOrEmpty(medUid) && medUid != player.PlayerUID) return;
            if (diet == null || !diet.Matches(itemslot.Itemstack, true, 0f)) return;

            handled = EnumHandling.PreventSubsequent;
            if (entity.Api.Side != EnumAppSide.Server) return;
            itemslot.TakeOut(1);
            itemslot.MarkDirty();
            Bond(player.PlayerUID, true);
        }

        /// <summary>Fallback for /lopbond: same LoP gate, no item needed. Returns null on success, else a reason.</summary>
        public string TryBondByCommand(IServerPlayer player)
        {
            if (!entity.Alive) return Lang.Get("loppetaicompat:cmd-dead");
            if (!IsLoPTame) return Lang.Get("loppetaicompat:cmd-not-tame", Gen, bondMinGeneration);
            if (!string.IsNullOrEmpty(OwnerId)) return OwnerId == player.PlayerUID ? Lang.Get("loppetaicompat:cmd-already-yours") : Lang.Get("loppetaicompat:cmd-owned");
            string medUid = MedallionOwnerUid;
            if (!string.IsNullOrEmpty(medUid) && medUid != player.PlayerUID) return Lang.Get("loppetaicompat:cmd-owned");
            Bond(player.PlayerUID, true);
            return null;
        }

        public override void OnEntityReceiveDamage(DamageSource damageSource, ref float damage)
        {
            // PetAI's rules (owner cannot hurt pet, fall damage off, PvP) apply to bonded dinos only; wild LoP dinos untouched
            if (!Cfg.ApplyPetAIDamageRules || !IsBonded) return;
            base.OnEntityReceiveDamage(damageSource, ref damage);
        }

        public override WorldInteraction[] GetInteractionHelp(IClientWorldAccessor world, EntitySelection es, IClientPlayer player, ref EnumHandling handled)
        {
            return Array.Empty<WorldInteraction>();
        }

        public override void GetInfoText(StringBuilder infotext)
        {
            if (IsBonded) { base.GetInfoText(infotext); return; }
            if (entity.Alive && IsLoPTame) infotext.AppendLine(Lang.Get("loppetaicompat:info-bondable"));
        }

        public override void OnEntityDespawn(EntityDespawnData despawn)
        {
            entity.World.UnregisterGameTickListener(syncListenerId);
            base.OnEntityDespawn(despawn);
        }
    }
}
