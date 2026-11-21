using Hannibal.Backoffice.Api.Socle;
using Hannibal.Backoffice.Application.Catalog;
using Hannibal.Backoffice.Domain.Identity;

namespace Hannibal.Backoffice.Api.Presentation;

public sealed record ShipClassBody(
    string Code,
    string Label,
    int MinSpeedKnots,
    int MaxSpeedKnots,
    double TurnRadiusMeters,
    double LengthMeters);

public sealed record ShipClassListBody(IReadOnlyList<ShipClassBody> Classes);

public sealed record UpdateShipClassBody(string Label, int MinSpeedKnots, int MaxSpeedKnots, double TurnRadiusMeters, double LengthMeters);

public sealed record ShipViewBody(Guid Id, string CallSign, string ClassCode, bool Active, DateTimeOffset CreatedAt, DateTimeOffset? RetiredAt);

public sealed record ShipListBody(IReadOnlyList<ShipViewBody> Ships);

public sealed record CreateShipBody(string CallSign, string ClassCode);

public sealed record ChangeShipClassBody(string ClassCode);

/// <summary>Classes et navires (Lot 7.3), réservés à <c>catalog:manage</c>.</summary>
public static class ShipEndpoints
{
    public static IEndpointRouteBuilder MapShips(this IEndpointRouteBuilder app)
    {
        var classes = app.MapGroup("/v1/ship-classes").WithTags("navires").RequireAuthorization(Permission.CatalogManage);

        classes.MapGet("", async (Ships handler, CancellationToken ct) =>
            Results.Json(new ShipClassListBody([.. (await handler.ListClassesAsync(ct).ConfigureAwait(false)).Select(ToView)]), Json.Options))
            .Produces<ShipClassListBody>();

        classes.MapPost("", async (ShipClassBody body, Ships handler, CancellationToken ct) =>
        {
            var created = await handler.CreateClassAsync(
                new ShipClass(body.Code ?? "", body.Label ?? "", body.MinSpeedKnots, body.MaxSpeedKnots, body.TurnRadiusMeters, body.LengthMeters),
                ct).ConfigureAwait(false);
            return Results.Json(ToView(created), Json.Options, statusCode: StatusCodes.Status201Created);
        }).Produces<ShipClassBody>(StatusCodes.Status201Created);

        classes.MapPut("/{code}", async (string code, UpdateShipClassBody body, Ships handler, CancellationToken ct) =>
            Results.Json(
                ToView(await handler.UpdateClassAsync(
                    new ShipClass(code, body.Label ?? "", body.MinSpeedKnots, body.MaxSpeedKnots, body.TurnRadiusMeters, body.LengthMeters),
                    ct).ConfigureAwait(false)),
                Json.Options))
            .Produces<ShipClassBody>();

        var ships = app.MapGroup("/v1/ships").WithTags("navires").RequireAuthorization(Permission.CatalogManage);

        ships.MapGet("", async (Ships handler, CancellationToken ct) =>
            Results.Json(new ShipListBody([.. (await handler.ListShipsAsync(ct).ConfigureAwait(false)).Select(ToView)]), Json.Options))
            .Produces<ShipListBody>();

        ships.MapPost("", async (CreateShipBody body, Ships handler, CancellationToken ct) =>
        {
            var created = await handler.CreateShipAsync(body.CallSign ?? "", body.ClassCode ?? "", ct).ConfigureAwait(false);
            return Results.Json(ToView(created), Json.Options, statusCode: StatusCodes.Status201Created);
        }).Produces<ShipViewBody>(StatusCodes.Status201Created);

        ships.MapPut("/{id:guid}/class", async (Guid id, ChangeShipClassBody body, Ships handler, CancellationToken ct) =>
            Results.Json(ToView(await handler.ChangeClassAsync(id, body.ClassCode ?? "", ct).ConfigureAwait(false)), Json.Options))
            .Produces<ShipViewBody>();

        ships.MapPost("/{id:guid}/retire", async (Guid id, Ships handler, CancellationToken ct) =>
            Results.Json(ToView(await handler.RetireAsync(id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<ShipViewBody>();

        ships.MapPost("/{id:guid}/reactivate", async (Guid id, Ships handler, CancellationToken ct) =>
            Results.Json(ToView(await handler.ReactivateAsync(id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<ShipViewBody>();

        return app;
    }

    private static ShipClassBody ToView(ShipClass c) =>
        new(c.Code, c.Label, c.MinSpeedKnots, c.MaxSpeedKnots, c.TurnRadiusMeters, c.LengthMeters);

    private static ShipViewBody ToView(Ship s) => new(s.Id, s.CallSign, s.ClassCode, s.RetiredAt is null, s.CreatedAt, s.RetiredAt);
}
