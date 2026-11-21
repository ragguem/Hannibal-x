using System.Security.Claims;
using Hannibal.Backoffice.Api.Socle;
using Hannibal.Backoffice.Application.Catalog;
using Hannibal.Backoffice.Domain.Identity;

namespace Hannibal.Backoffice.Api.Presentation;

public sealed record ScenarioEntryBody(
    string Id,
    string Title,
    string Level,
    int? PublishedVersion,
    int LatestVersion,
    DateTimeOffset? ArchivedAt);

public sealed record ScenarioCatalogBody(IReadOnlyList<ScenarioEntryBody> Scenarios);

public sealed record ImportScenarioBody(string Yaml);

public sealed record PublishScenarioBody(int Version);

/// <summary>
/// Scénarios du catalogue (Lot 7.4), réservés à <c>catalog:manage</c>. <c>/v1/scenarios</c> reste relayé vers
/// <c>apps/api</c> jusqu'à la photo de mission (Lot 7.5).
/// </summary>
public static class ScenarioCatalogEndpoints
{
    public static IEndpointRouteBuilder MapScenarioCatalog(this IEndpointRouteBuilder app)
    {
        var scenarios = app.MapGroup("/v1/catalog/scenarios").WithTags("scénarios").RequireAuthorization(Permission.CatalogManage);

        scenarios.MapGet("", async (Scenarios handler, CancellationToken ct) =>
            Results.Json(new ScenarioCatalogBody([.. (await handler.ListAsync(ct).ConfigureAwait(false)).Select(ToView)]), Json.Options))
            .Produces<ScenarioCatalogBody>();

        scenarios.MapPost("", async (ImportScenarioBody body, Scenarios handler, HttpContext context, CancellationToken ct) =>
        {
            var actor = Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!);
            var entry = await handler.ImportAsync(body.Yaml ?? "", actor, ct).ConfigureAwait(false);
            return Results.Json(ToView(entry), Json.Options, statusCode: StatusCodes.Status201Created);
        }).Produces<ScenarioEntryBody>(StatusCodes.Status201Created);

        scenarios.MapPost("/{id}/publish", async (string id, PublishScenarioBody body, Scenarios handler, CancellationToken ct) =>
            Results.Json(ToView(await handler.PublishAsync(id, body.Version, ct).ConfigureAwait(false)), Json.Options))
            .Produces<ScenarioEntryBody>();

        scenarios.MapPost("/{id}/archive", async (string id, Scenarios handler, CancellationToken ct) =>
            Results.Json(ToView(await handler.ArchiveAsync(id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<ScenarioEntryBody>();

        scenarios.MapGet("/{id}/versions/{version:int}/yaml", async (string id, int version, Scenarios handler, HttpContext context, CancellationToken ct) =>
        {
            var yaml = await handler.ExportAsync(id, version, ct).ConfigureAwait(false);
            context.Response.Headers.ContentDisposition = $"attachment; filename=\"{id}.v{version}.yaml\"";
            return Results.Text(yaml, "application/yaml; charset=utf-8");
        }).Produces<string>(StatusCodes.Status200OK, "application/yaml");

        return app;
    }

    private static ScenarioEntryBody ToView(ScenarioEntry e) => new(e.Id, e.Title, e.Level, e.PublishedVersion, e.LatestVersion, e.ArchivedAt);
}
