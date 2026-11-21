using System.Globalization;
using System.Text.Json;
using Hannibal.Backoffice.Application.Catalog;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;

namespace Hannibal.Backoffice.Application.Planning;

public sealed record ParticipantPlan(Guid UserId, string Ship, string GameRole);

public sealed record MissionPlan(string ScenarioId, string PlayerShip, bool Autopilot, bool ManualHelm, IReadOnlyList<ParticipantPlan> Participants);

public sealed record ParticipantView(Guid UserId, string Username, string Ship, string GameRole);

public sealed record MissionView(
    Guid Id,
    string ScenarioId,
    int ScenarioVersion,
    string ScenarioTitle,
    string PlayerShip,
    bool Autopilot,
    bool ManualHelm,
    string State,
    DateTimeOffset CreatedAt,
    DateTimeOffset? LaunchedAt,
    DateTimeOffset? ArchivedAt,
    string? RunPhase,
    DateTimeOffset? FinishedAt,
    IReadOnlyList<ParticipantView> Participants);

public sealed record MissionPage(IReadOnlyList<MissionView> Missions, string? NextCursor);

public sealed record PlayableScenario(
    string Id,
    string Title,
    string? Level,
    int DurationS,
    string? Summary,
    string? Briefing,
    IReadOnlyList<string> PlayableShips,
    string GuideShip);

public sealed record Player(Guid Id, string Username);

/// <summary>
/// Planification (Lot 7.5) : la mission fige une version publiée du scénario ; au lancement, le back-office envoie à
/// <c>apps/api</c> une photo (document et caractéristiques des navires) et ne relit plus le catalogue.
/// </summary>
public sealed class MissionPlanner(
    IMissionPlanning planning,
    IMissionRuns runs,
    IMissionLauncher launcher,
    IScenarioCatalog scenarios,
    IShipCatalog ships,
    IUserDirectory users,
    TimeProvider time)
{
    public const int MaxPageSize = 50;

    public async Task<IReadOnlyList<PlayableScenario>> PlayableScenariosAsync(CancellationToken cancellationToken)
    {
        var playable = new List<PlayableScenario>();
        foreach (var entry in await scenarios.ListAsync(cancellationToken).ConfigureAwait(false))
        {
            if (entry is { ArchivedAt: null, PublishedVersion: { } version }
                && await scenarios.DocumentOfAsync(entry.Id, version, cancellationToken).ConfigureAwait(false) is { } json)
            {
                playable.Add(Summarize(json));
            }
        }
        return playable;
    }

    public async Task<IReadOnlyList<Player>> PlayersAsync(CancellationToken cancellationToken) =>
        [.. (await users.ListAsync(cancellationToken).ConfigureAwait(false))
            .Where(u => u.DisabledAt is null)
            .OrderBy(u => u.Username, StringComparer.Ordinal)
            .Select(u => new Player(u.Id, u.Username))];

    public async Task<MissionView> PlanAsync(MissionPlan plan, Guid plannedBy, CancellationToken cancellationToken)
    {
        var entry = await scenarios.FindAsync(plan.ScenarioId, cancellationToken).ConfigureAwait(false);
        if (entry is not { ArchivedAt: null, PublishedVersion: { } version })
        {
            throw Invalid("scénario non publié", "Ce scénario n'est pas publié.");
        }
        var fleet = FleetOf(await DocumentAsync(entry.Id, version, cancellationToken).ConfigureAwait(false));
        var active = await ActiveShipsAsync(cancellationToken).ConfigureAwait(false);
        var player = FleetShip(plan.PlayerShip, fleet, active);
        var participants = new List<Participant>();
        foreach (var p in plan.Participants)
        {
            if (!IdentityCatalog.GameRoles.Any(g => g.Code == p.GameRole))
            {
                throw Invalid("rôle de jeu inconnu", $"Rôle de jeu inconnu : {p.GameRole}.");
            }
            if (await users.FindAsync(p.UserId, cancellationToken).ConfigureAwait(false) is not { DisabledAt: null })
            {
                throw Invalid("participant inconnu", "Participant inconnu ou désactivé.");
            }
            participants.Add(new Participant(p.UserId, FleetShip(p.Ship, fleet, active).Id, p.GameRole));
        }
        if (participants.DistinctBy(p => p.ShipId).Count() != participants.Count
            || participants.DistinctBy(p => p.UserId).Count() != participants.Count)
        {
            throw Invalid("participant en double", "Un navire ou un participant n'apparaît qu'une fois.");
        }
        var mission = new PlannedMission(
            Guid.NewGuid(), entry.Id, version, player.Id, plan.Autopilot, plan.ManualHelm, MissionState.Planned, plannedBy,
            time.GetUtcNow(), null, null, participants);
        await planning.AddAsync(mission, cancellationToken).ConfigureAwait(false);
        return (await ViewsAsync([mission], cancellationToken).ConfigureAwait(false))[0];
    }

    public Task<MissionView> ReadyAsync(Guid id, CancellationToken cancellationToken) =>
        TransitionAsync(id, [MissionState.Planned], MissionState.Ready, cancellationToken);

    public Task<MissionView> ArchiveAsync(Guid id, CancellationToken cancellationToken) =>
        TransitionAsync(id, [MissionState.Planned, MissionState.Ready, MissionState.Running], MissionState.Archived, cancellationToken);

    /// <summary>
    /// Rejouable : une mission déjà lancée est rendue telle quelle ; restée <c>launching</c> (apps/api injoignable),
    /// elle est relancée et <c>apps/api</c> ne la démarre pas deux fois. Un refus d'apps/api la remet <c>ready</c>.
    /// </summary>
    public async Task<MissionView> LaunchAsync(Guid id, string launchedBy, CancellationToken cancellationToken)
    {
        var mission = await RequireAsync(id, cancellationToken).ConfigureAwait(false);
        if (mission.State == MissionState.Running)
        {
            return (await ViewsAsync([mission], cancellationToken).ConfigureAwait(false))[0];
        }
        if (mission.State != MissionState.Launching
            && !await planning.TransitionAsync(id, [MissionState.Planned, MissionState.Ready], MissionState.Launching, time.GetUtcNow(), cancellationToken).ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.Conflict, "mission non lançable", "Cette mission ne peut plus être lancée.");
        }
        try
        {
            var snapshot = await SnapshotAsync(mission, launchedBy, cancellationToken).ConfigureAwait(false);
            await launcher.LaunchAsync(id, snapshot, cancellationToken).ConfigureAwait(false);
        }
        catch (RuleViolation e) when (e.Kind is not RuleKind.Unavailable)
        {
            await planning.TransitionAsync(id, [MissionState.Launching], MissionState.Ready, time.GetUtcNow(), cancellationToken).ConfigureAwait(false);
            throw;
        }
        await planning.TransitionAsync(id, [MissionState.Launching], MissionState.Running, time.GetUtcNow(), cancellationToken).ConfigureAwait(false);
        return await ReadAsync(id, cancellationToken).ConfigureAwait(false);
    }

    public async Task<MissionView> ReadAsync(Guid id, CancellationToken cancellationToken) =>
        (await ViewsAsync([await RequireAsync(id, cancellationToken).ConfigureAwait(false)], cancellationToken).ConfigureAwait(false))[0];

    public async Task<MissionPage> HistoryAsync(string? cursor, int limit, CancellationToken cancellationToken)
    {
        if (limit is < 1 or > MaxPageSize)
        {
            throw Invalid("taille de page refusée", $"Entre 1 et {MaxPageSize} missions par page.");
        }
        var page = await planning.PageAsync(ParseCursor(cursor), limit + 1, cancellationToken).ConfigureAwait(false);
        var shown = page.Take(limit).ToList();
        var next = page.Count > limit ? FormatCursor(shown[^1]) : null;
        return new MissionPage(await ViewsAsync(shown, cancellationToken).ConfigureAwait(false), next);
    }

    private async Task<MissionView> TransitionAsync(Guid id, string[] from, string to, CancellationToken cancellationToken)
    {
        await RequireAsync(id, cancellationToken).ConfigureAwait(false);
        if (!await planning.TransitionAsync(id, from, to, time.GetUtcNow(), cancellationToken).ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.Conflict, $"transition vers {to} refusée");
        }
        return await ReadAsync(id, cancellationToken).ConfigureAwait(false);
    }

    private async Task<MissionSnapshot> SnapshotAsync(PlannedMission mission, string launchedBy, CancellationToken cancellationToken)
    {
        var json = await DocumentAsync(mission.ScenarioId, mission.ScenarioVersion, cancellationToken).ConfigureAwait(false);
        var active = await ActiveShipsAsync(cancellationToken).ConfigureAwait(false);
        var classes = (await ships.ListClassesAsync(cancellationToken).ConfigureAwait(false)).ToDictionary(c => c.Code, StringComparer.Ordinal);
        var fleet = FleetOf(json);
        var snapshot = new List<ShipSnapshot>();
        foreach (var callSign in fleet)
        {
            var ship = FleetShip(callSign, fleet, active);
            var shipClass = classes[ship.ClassCode];
            snapshot.Add(new ShipSnapshot(
                ship.CallSign, shipClass.Code, shipClass.MinSpeedKnots, shipClass.MaxSpeedKnots, shipClass.TurnRadiusMeters, shipClass.LengthMeters));
        }
        var player = active.Values.SingleOrDefault(s => s.Id == mission.PlayerShipId)
            ?? throw Invalid("navire joué retiré", "Le navire joué a été retiré du service.");
        var operatorId = mission.Participants.FirstOrDefault(p => p.ShipId == player.Id) is { } holder
            && await users.FindAsync(holder.UserId, cancellationToken).ConfigureAwait(false) is { } user
            ? user.Username
            : launchedBy;
        return new MissionSnapshot(mission.ScenarioVersion, json, player.CallSign, operatorId, mission.Autopilot, mission.ManualHelm, snapshot);
    }

    private async Task<IReadOnlyList<MissionView>> ViewsAsync(IReadOnlyList<PlannedMission> missions, CancellationToken cancellationToken)
    {
        if (missions.Count == 0)
        {
            return [];
        }
        var shipNames = (await ships.ListShipsAsync(cancellationToken).ConfigureAwait(false)).ToDictionary(s => s.Id, s => s.CallSign);
        var usernames = (await users.ListAsync(cancellationToken).ConfigureAwait(false)).ToDictionary(u => u.Id, u => u.Username);
        var titles = (await scenarios.ListAsync(cancellationToken).ConfigureAwait(false)).ToDictionary(s => s.Id, s => s.Title, StringComparer.Ordinal);
        var played = await runs.FindAsync([.. missions.Select(m => m.Id)], cancellationToken).ConfigureAwait(false);
        return
        [
            .. missions.Select(m => new MissionView(
                m.Id,
                m.ScenarioId,
                m.ScenarioVersion,
                titles.GetValueOrDefault(m.ScenarioId, m.ScenarioId),
                shipNames.GetValueOrDefault(m.PlayerShipId, "?"),
                m.Autopilot,
                m.ManualHelm,
                m.State,
                m.CreatedAt,
                m.LaunchedAt,
                m.ArchivedAt,
                played.GetValueOrDefault(m.Id)?.Phase,
                played.GetValueOrDefault(m.Id)?.FinishedAt,
                [.. m.Participants.Select(p => new ParticipantView(
                    p.UserId, usernames.GetValueOrDefault(p.UserId, "?"), shipNames.GetValueOrDefault(p.ShipId, "?"), p.GameRole))])),
        ];
    }

    private async Task<PlannedMission> RequireAsync(Guid id, CancellationToken cancellationToken) =>
        await planning.FindAsync(id, cancellationToken).ConfigureAwait(false)
        ?? throw new RuleViolation(RuleKind.NotFound, "mission inconnue");

    private async Task<string> DocumentAsync(string id, int version, CancellationToken cancellationToken) =>
        await scenarios.DocumentOfAsync(id, version, cancellationToken).ConfigureAwait(false)
        ?? throw new RuleViolation(RuleKind.NotFound, "version de scénario inconnue");

    private async Task<Dictionary<string, Ship>> ActiveShipsAsync(CancellationToken cancellationToken) =>
        (await ships.ListShipsAsync(cancellationToken).ConfigureAwait(false))
            .Where(s => s.RetiredAt is null)
            .ToDictionary(s => s.CallSign, StringComparer.Ordinal);

    private static Ship FleetShip(string callSign, IReadOnlyList<string> fleet, Dictionary<string, Ship> active) =>
        fleet.Contains(callSign, StringComparer.Ordinal) && active.TryGetValue(callSign, out var ship)
            ? ship
            : throw Invalid("navire hors flotte", $"Le navire « {callSign} » n'est pas dans la flotte du scénario ou n'est plus en service.");

    private static List<string> FleetOf(string json)
    {
        using var document = JsonDocument.Parse(json);
        return [.. document.RootElement.GetProperty("flotte").EnumerateArray().Select(s => s.GetProperty("nom").GetString()!)];
    }

    private static PlayableScenario Summarize(string json)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        string? Text(string name) => root.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() : null;
        var fleet = root.GetProperty("flotte").EnumerateArray()
            .Select(s => (Name: s.GetProperty("nom").GetString()!, Role: s.GetProperty("role").GetString()))
            .ToList();
        var guide = fleet.First(s => s.Role == "guide").Name;
        return new PlayableScenario(
            Text("id")!,
            Text("titre")!,
            Text("niveau"),
            (int)root.GetProperty("duree_s").GetDouble(),
            Text("resume"),
            Text("briefing"),
            [guide, .. fleet.Select(s => s.Name).Where(n => n != guide)],
            guide);
    }

    private static string FormatCursor(PlannedMission mission) =>
        string.Create(CultureInfo.InvariantCulture, $"{mission.CreatedAt.UtcTicks}_{mission.Id:N}");

    private static MissionCursor? ParseCursor(string? cursor)
    {
        if (string.IsNullOrEmpty(cursor))
        {
            return null;
        }
        var parts = cursor.Split('_');
        return parts.Length == 2
            && long.TryParse(parts[0], NumberStyles.None, CultureInfo.InvariantCulture, out var ticks)
            && Guid.TryParseExact(parts[1], "N", out var id)
            ? new MissionCursor(new DateTimeOffset(ticks, TimeSpan.Zero), id)
            : throw Invalid("curseur illisible", "Curseur de pagination illisible.");
    }

    private static RuleViolation Invalid(string detail, string message) => new(RuleKind.Invalid, detail, message);
}
