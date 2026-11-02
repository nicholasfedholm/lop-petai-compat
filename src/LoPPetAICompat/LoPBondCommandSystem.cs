using Vintagestory.API.Common;
using Vintagestory.API.Config;
using Vintagestory.API.Server;

namespace LoPPetAICompat
{
    /// <summary>
    /// /lopbond: bond the LoP dinosaur you are looking at, if LoP already considers it tame.
    /// Fallback for when another behavior (mount, accessories) consumes the hand-feed right click.
    /// </summary>
    public class LoPBondCommandSystem : ModSystem
    {
        public override bool ShouldLoad(EnumAppSide forSide) => forSide == EnumAppSide.Server;

        public override void StartServerSide(ICoreServerAPI api)
        {
            api.ChatCommands.Create("lopbond")
                .WithDescription("Bond the Legacy of the Phanerozoic dinosaur you are looking at (PetAI owner), if it is tame by LoP's generation rules.")
                .RequiresPrivilege(Privilege.chat)
                .RequiresPlayer()
                .HandleWith(args =>
                {
                    var plr = args.Caller.Player as IServerPlayer;
                    // CurrentEntitySelection is only refreshed by interact packets on the server, so fall back to the
                    // nearest unbonded LoP-tame dino within 6 blocks
                    var beh = plr?.CurrentEntitySelection?.Entity?.GetBehavior<EntityBehaviorLoPTameable>();
                    if (beh == null || beh.IsBonded)
                    {
                        var near = api.World.GetNearestEntity(plr.Entity.Pos.XYZ, 6, 6, e =>
                            e.Alive && e.GetBehavior<EntityBehaviorLoPTameable>() is { } b && b.IsLoPTame && !b.IsBonded);
                        beh = near?.GetBehavior<EntityBehaviorLoPTameable>() ?? beh;
                    }
                    if (beh == null) return TextCommandResult.Error(Lang.Get("loppetaicompat:cmd-look-at-dino"));
                    string err = beh.TryBondByCommand(plr);
                    return err == null ? TextCommandResult.Success() : TextCommandResult.Error(err);
                });
        }
    }
}
