using System.Security.Claims;
using Hannibal.Backoffice.Api.Socle;
using Hannibal.Backoffice.Application.Planning;
using Hannibal.Backoffice.Domain.Identity;

namespace Hannibal.Backoffice.Api.Presentation;

public sealed record ScenarioSummaryBody(
    string Id,
    string Title,
    string? Level,
    int DurationS,
    string? Summary,
    string? Briefing,
    IReadOnlyList<string> PlayableShips,
    string GuideShip);

public sealed record ParticipantBody(Guid UserId, string Ship, string GameRole);

public sealed record PlanMissionBody(string ScenarioId, string PlayerShip, bool Autopilot, bool ManualHelm, IReadOnlyList<ParticipantBody>? Participants);

public sealed record ParticipantViewBody(Guid UserId, string Username, string Ship, string GameRole);

public sealed record PlannedMissionBody(
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
    IReadOnlyList<ParticipantViewBody> Participants);

public sealed record MissionHistoryBody(IReadOnlyList<PlannedMissionBody> Missions, string? NextCursor);

public sealed record PlayerBody(Guid Id, string Username);

public sealed record GameRoleBody(string Code, string Label);

public sealed record PlanningOptionsBody(IReadOnlyList<PlayerBody> Players, IReadOnlyList<GameRoleBody> GameRoles);

/// <summary>
/// Scénarios jouables et planification (Lot 7.5). Le lancement envoie la photo à <c>apps/api</c> ; la mission se
/// joue ensuite par les routes relayées <c>/v1/missions/{id}/…</c>.
/// </summary>
public static class PlanningEndpoints
{
    public static IEndpointRouteBuilder MapPlanning(this IEndpointRouteBuilder app)
    {
        app.MapGet("/v1/scenarios", async (MissionPlanner planner, CancellationToken ct) =>
            Results.Json((await planner.PlayableScenariosAsync(ct).ConfigureAwait(false)).Select(s => new ScenarioSummaryBody(
                s.Id, s.Title, s.Level, s.DurationS, s.Summary, s.Briefing, s.PlayableShips, s.GuideShip)), Json.Options))
            .WithTags("planification").RequireAuthorization(Permission.MissionPlay)
            .Produces<IReadOnlyList<ScenarioSummaryBody>>();

        var planning = app.MapGroup("/v1/planning").WithTags("planification").RequireAuthorization(Permission.MissionPlan);

        planning.MapGet("/options", async (MissionPlanner planner, CancellationToken ct) =>
            Results.Json(new PlanningOptionsBody(
                [.. (await planner.PlayersAsync(ct).ConfigureAwait(false)).Select(p => new PlayerBody(p.Id, p.Username))],
                [.. IdentityCatalog.GameRoles.Select(g => new GameRoleBody(g.Code, g.Label))]), Json.Options))
            .Produces<PlanningOptionsBody>();

        planning.MapGet("/missions", async (string? cursor, int? limit, MissionPlanner planner, CancellationToken ct) =>
        {
            var page = await planner.HistoryAsync(cursor, limit ?? 20, ct).ConfigureAwait(false);
            return Results.Json(new MissionHistoryBody([.. page.Missions.Select(ToBody)], page.NextCursor), Json.Options);
        }).Produces<MissionHistoryBody>();

        planning.MapPost("/missions", async (PlanMissionBody body, MissionPlanner planner, HttpContext context, CancellationToken ct) =>
        {
            var plan = new MissionPlan(
                body.ScenarioId ?? "",
                body.PlayerShip ?? "",
                body.Autopilot,
                body.ManualHelm,
                [.. (body.Participants ?? []).Select(p => new ParticipantPlan(p.UserId, p.Ship ?? "", p.GameRole ?? ""))]);
            var mission = await planner.PlanAsync(plan, ActorId(context), ct).ConfigureAwait(false);
            return Results.Json(ToBody(mission), Json.Options, statusCode: StatusCodes.Status201Created);
        }).Produces<PlannedMissionBody>(StatusCodes.Status201Created);

        planning.MapGet("/missions/{id:guid}", async (Guid id, MissionPlanner planner, CancellationToken ct) =>
            Results.Json(ToBody(await planner.ReadAsync(id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<PlannedMissionBody>();

        planning.MapPost("/missions/{id:guid}/ready", async (Guid id, MissionPlanner planner, CancellationToken ct) =>
            Results.Json(ToBody(await planner.ReadyAsync(id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<PlannedMissionBody>();

        planning.MapPost("/missions/{id:guid}/launch", async (Guid id, MissionPlanner planner, HttpContext context, CancellationToken ct) =>
            Results.Json(ToBody(await planner.LaunchAsync(id, context.User.FindFirstValue(ClaimTypes.Name)!, ct).ConfigureAwait(false)), Json.Options))
            .Produces<PlannedMissionBody>();

        planning.MapPost("/missions/{id:guid}/archive", async (Guid id, MissionPlanner planner, CancellationToken ct) =>
            Results.Json(ToBody(await planner.ArchiveAsync(id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<PlannedMissionBody>();

        return app;
    }

    private static Guid ActorId(HttpContext context) => Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!);

    private static PlannedMissionBody ToBody(MissionView m) => new(
        m.Id,
        m.ScenarioId,
        m.ScenarioVersion,
        m.ScenarioTitle,
        m.PlayerShip,
        m.Autopilot,
        m.ManualHelm,
        m.State,
        m.CreatedAt,
        m.LaunchedAt,
        m.ArchivedAt,
        m.RunPhase,
        m.FinishedAt,
        [.. m.Participants.Select(p => new ParticipantViewBody(p.UserId, p.Username, p.Ship, p.GameRole))]);
}
