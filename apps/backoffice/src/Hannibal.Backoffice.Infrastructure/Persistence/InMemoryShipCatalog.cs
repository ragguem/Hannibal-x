using System.Collections.Concurrent;
using Hannibal.Backoffice.Application.Catalog;
using Hannibal.Backoffice.Domain.Catalog;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

/// <summary>Mode <c>fake</c> : le catalogue de <see cref="ShipCatalogSeed"/>, comme après le seed, perdu à l'arrêt.</summary>
public sealed class InMemoryShipCatalog : IShipCatalog
{
    private readonly ConcurrentDictionary<string, ShipClass> _classes = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<Guid, Ship> _ships = new();
    private readonly Lock _creation = new();

    public InMemoryShipCatalog()
    {
        foreach (var c in ShipCatalogSeed.Classes)
        {
            _classes[c.Code] = new ShipClass(c.Code, c.Label, c.MinSpeedKnots, c.MaxSpeedKnots, c.TurnRadiusMeters, c.LengthMeters);
        }
        foreach (var s in ShipCatalogSeed.Ships)
        {
            var ship = new Ship(Guid.CreateVersion7(), s.CallSign, s.ClassCode, DateTimeOffset.UtcNow, null);
            _ships[ship.Id] = ship;
        }
    }

    public Task<IReadOnlyList<ShipClass>> ListClassesAsync(CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<ShipClass>>([.. _classes.Values.OrderBy(c => c.Code, StringComparer.Ordinal)]);

    public Task<ShipClass?> FindClassAsync(string code, CancellationToken cancellationToken) =>
        Task.FromResult(_classes.GetValueOrDefault(code));

    public Task<bool> TryCreateClassAsync(ShipClass shipClass, CancellationToken cancellationToken) =>
        Task.FromResult(_classes.TryAdd(shipClass.Code, shipClass));

    public Task<bool> UpdateClassAsync(ShipClass shipClass, CancellationToken cancellationToken)
    {
        if (!_classes.ContainsKey(shipClass.Code))
        {
            return Task.FromResult(false);
        }
        _classes[shipClass.Code] = shipClass;
        return Task.FromResult(true);
    }

    public Task<IReadOnlyList<Ship>> ListShipsAsync(CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<Ship>>([.. _ships.Values.OrderBy(s => s.CallSign, StringComparer.Ordinal)]);

    public Task<Ship?> FindShipAsync(Guid id, CancellationToken cancellationToken) => Task.FromResult(_ships.GetValueOrDefault(id));

    public Task<bool> TryCreateShipAsync(Ship ship, CancellationToken cancellationToken)
    {
        lock (_creation)
        {
            if (_ships.Values.Any(s => s.CallSign == ship.CallSign))
            {
                return Task.FromResult(false);
            }
            _ships[ship.Id] = ship;
            return Task.FromResult(true);
        }
    }

    public Task<bool> SetShipClassAsync(Guid id, string classCode, CancellationToken cancellationToken) =>
        Task.FromResult(Update(id, s => s with { ClassCode = classCode }));

    public Task<bool> SetRetiredAtAsync(Guid id, DateTimeOffset? retiredAt, CancellationToken cancellationToken) =>
        Task.FromResult(Update(id, s => s with { RetiredAt = retiredAt }));

    private bool Update(Guid id, Func<Ship, Ship> change)
    {
        if (!_ships.TryGetValue(id, out var ship))
        {
            return false;
        }
        _ships[id] = change(ship);
        return true;
    }
}
