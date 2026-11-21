namespace Hannibal.Backoffice.Application.Catalog;

public sealed record ShipClass(
    string Code,
    string Label,
    int MinSpeedKnots,
    int MaxSpeedKnots,
    double TurnRadiusMeters,
    double LengthMeters);

public sealed record Ship(Guid Id, string CallSign, string ClassCode, DateTimeOffset CreatedAt, DateTimeOffset? RetiredAt);

/// <summary>Classes et navires du schéma <c>catalog</c>. Les écritures renvoient <c>false</c> si la ligne n'existe pas ou existe déjà.</summary>
public interface IShipCatalog
{
    Task<IReadOnlyList<ShipClass>> ListClassesAsync(CancellationToken cancellationToken);

    Task<ShipClass?> FindClassAsync(string code, CancellationToken cancellationToken);

    Task<bool> TryCreateClassAsync(ShipClass shipClass, CancellationToken cancellationToken);

    Task<bool> UpdateClassAsync(ShipClass shipClass, CancellationToken cancellationToken);

    Task<IReadOnlyList<Ship>> ListShipsAsync(CancellationToken cancellationToken);

    Task<Ship?> FindShipAsync(Guid id, CancellationToken cancellationToken);

    Task<bool> TryCreateShipAsync(Ship ship, CancellationToken cancellationToken);

    Task<bool> SetShipClassAsync(Guid id, string classCode, CancellationToken cancellationToken);

    Task<bool> SetRetiredAtAsync(Guid id, DateTimeOffset? retiredAt, CancellationToken cancellationToken);
}
