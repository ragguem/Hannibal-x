namespace Hannibal.Backoffice.Application.Planning;

/// <summary>États écrits par le back-office ; la fin d'une mission jouée se lit dans <see cref="IMissionRuns"/>.</summary>
public static class MissionState
{
    public const string Planned = "planned";
    public const string Ready = "ready";
    public const string Launching = "launching";
    public const string Running = "running";
    public const string Archived = "archived";
}

public sealed record Participant(Guid UserId, Guid ShipId, string GameRole);

public sealed record PlannedMission(
    Guid Id,
    string ScenarioId,
    int ScenarioVersion,
    Guid PlayerShipId,
    bool Autopilot,
    bool ManualHelm,
    string State,
    Guid PlannedBy,
    DateTimeOffset CreatedAt,
    DateTimeOffset? LaunchedAt,
    DateTimeOffset? ArchivedAt,
    IReadOnlyList<Participant> Participants);

/// <summary>Position dans l'historique, du plus récent au plus ancien ; l'horodatage est à la microseconde.</summary>
public sealed record MissionCursor(DateTimeOffset CreatedAt, Guid Id);

public interface IMissionPlanning
{
    Task AddAsync(PlannedMission mission, CancellationToken cancellationToken);

    Task<PlannedMission?> FindAsync(Guid id, CancellationToken cancellationToken);

    /// <summary>Passe à <paramref name="to"/> si l'état courant est dans <paramref name="from"/> ; <c>false</c> sinon.</summary>
    Task<bool> TransitionAsync(Guid id, IReadOnlyCollection<string> from, string to, DateTimeOffset at, CancellationToken cancellationToken);

    Task<IReadOnlyList<PlannedMission>> PageAsync(MissionCursor? after, int limit, CancellationToken cancellationToken);
}

public sealed record MissionRunSummary(Guid MissionId, string Phase, DateTimeOffset StartedAt, DateTimeOffset? FinishedAt);

/// <summary>Vue <c>ops_read.mission_runs</c> publiée par <c>apps/api</c> : le back-office ne lit jamais <c>ops</c>.</summary>
public interface IMissionRuns
{
    Task<IReadOnlyDictionary<Guid, MissionRunSummary>> FindAsync(IReadOnlyCollection<Guid> missionIds, CancellationToken cancellationToken);
}

public sealed record ShipSnapshot(string CallSign, string ClassCode, int MinSpeedKnots, int MaxSpeedKnots, double TurnRadiusMeters, double LengthMeters);

public sealed record MissionSnapshot(
    int ScenarioVersion,
    string ScenarioJson,
    string PlayerShip,
    string Operator,
    bool Autopilot,
    bool ManualHelm,
    IReadOnlyList<ShipSnapshot> Ships);

/// <summary><c>PUT /internal/missions/{id}/run</c> d'<c>apps/api</c> : rejoué, il rend la mission déjà lancée.</summary>
public interface IMissionLauncher
{
    /// <exception cref="RuleViolation">Refus d'<c>apps/api</c> (422 ou 409), ou service injoignable (503).</exception>
    Task LaunchAsync(Guid missionId, MissionSnapshot snapshot, CancellationToken cancellationToken);
}
