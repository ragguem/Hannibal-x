namespace Hannibal.Backoffice.Infrastructure.Persistence;

public sealed class ShipClassRow
{
    public required string Code { get; set; }
    public required string Label { get; set; }
    public int MinSpeedKnots { get; set; }
    public int MaxSpeedKnots { get; set; }
    public double TurnRateDegreesPerSecond { get; set; }
}

public sealed class ShipRow
{
    public Guid Id { get; set; }
    public required string CallSign { get; set; }
    public required string ClassCode { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset? RetiredAt { get; set; }
}

public sealed class ScenarioRow
{
    public required string Id { get; set; }
    public required string Title { get; set; }
    public required string Level { get; set; }
    public int? PublishedVersion { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset? ArchivedAt { get; set; }
}

public sealed class ScenarioVersionRow
{
    public required string ScenarioId { get; set; }
    public int Version { get; set; }
    public required string Document { get; set; }
    public required string ContentSha256 { get; set; }
    public Guid ImportedBy { get; set; }
    public DateTimeOffset ImportedAt { get; set; }
}

public sealed class MissionRow
{
    public Guid Id { get; set; }
    public required string ScenarioId { get; set; }
    public int ScenarioVersion { get; set; }
    public required string State { get; set; }
    public string? Runner { get; set; }
    public Guid PlannedBy { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset? LaunchedAt { get; set; }
    public DateTimeOffset? ArchivedAt { get; set; }
    public List<MissionParticipantRow> Participants { get; set; } = [];
}

public sealed class MissionParticipantRow
{
    public Guid MissionId { get; set; }
    public Guid ShipId { get; set; }
    public Guid UserId { get; set; }
    public required string GameRoleCode { get; set; }
}
