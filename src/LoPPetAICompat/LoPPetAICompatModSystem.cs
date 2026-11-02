using Vintagestory.API.Common;

namespace LoPPetAICompat
{
    /// <summary>
    /// Registers the LoP-aware tameable behavior. All per-family wiring is JSON patches in assets/loppetaicompat/patches.
    /// </summary>
    public class LoPPetAICompatModSystem : ModSystem
    {
        public static LoPPetAICompatConfig Config { get; private set; } = new LoPPetAICompatConfig();

        public override double ExecuteOrder() => 0.05;

        public override void Start(ICoreAPI api)
        {
            try
            {
                Config = api.LoadModConfig<LoPPetAICompatConfig>("loppetaicompat.json");
                if (Config == null)
                {
                    Config = new LoPPetAICompatConfig();
                    api.StoreModConfig(Config, "loppetaicompat.json");
                }
            }
            catch (System.Exception e)
            {
                api.Logger.Error("[loppetaicompat] Bad config, using defaults: {0}", e.Message);
                Config = new LoPPetAICompatConfig();
            }
            api.RegisterEntityBehaviorClass("loptameable", typeof(EntityBehaviorLoPTameable));
        }
    }

    public class LoPPetAICompatConfig
    {
        /// <summary>Allow PetAI's revive item (PetConfig Resurrectors) on a dead bonded dino, owner only. Off by default: LoP death/decay/butchering interaction not runtime-tested.</summary>
        public bool AllowRevive = false;
        /// <summary>Apply PetAI's petMaxHpModifier and owner/fall/PvP damage rules to bonded dinos. Wild dinos are never affected.</summary>
        public bool ApplyPetAIDamageRules = true;
        /// <summary>Server sync interval (ms) between LoP state and PetAI domestication state.</summary>
        public int SyncIntervalMs = 3000;
        /// <summary>Fallback bond generation when a family has no ownable behavior with minGeneration.</summary>
        public int FallbackMinGeneration = 10;
    }
}
