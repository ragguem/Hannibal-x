using Hannibal.Backoffice.Application.Catalog;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

public sealed class EfShipCatalog(BackofficeDbContext dbContext) : IShipCatalog
{
    public async Task<IReadOnlyList<ShipClass>> ListClassesAsync(CancellationToken cancellationToken) =>
        await dbContext.ShipClasses.AsNoTracking()
            .OrderBy(c => c.Code)
            .Select(c => new ShipClass(c.Code, c.Label, c.MinSpeedKnots, c.MaxSpeedKnots, c.TurnRadiusMeters, c.LengthMeters))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

    public async Task<ShipClass?> FindClassAsync(string code, CancellationToken cancellationToken) =>
        await dbContext.ShipClasses.AsNoTracking()
            .Where(c => c.Code == code)
            .Select(c => new ShipClass(c.Code, c.Label, c.MinSpeedKnots, c.MaxSpeedKnots, c.TurnRadiusMeters, c.LengthMeters))
            .SingleOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

    public Task<bool> TryCreateClassAsync(ShipClass shipClass, CancellationToken cancellationToken)
    {
        dbContext.ShipClasses.Add(new ShipClassRow
        {
            Code = shipClass.Code,
            Label = shipClass.Label,
            MinSpeedKnots = shipClass.MinSpeedKnots,
            MaxSpeedKnots = shipClass.MaxSpeedKnots,
            TurnRadiusMeters = shipClass.TurnRadiusMeters,
            LengthMeters = shipClass.LengthMeters,
        });
        return TrySaveAsync(cancellationToken);
    }

    public async Task<bool> UpdateClassAsync(ShipClass shipClass, CancellationToken cancellationToken) =>
        await dbContext.ShipClasses.Where(c => c.Code == shipClass.Code)
            .ExecuteUpdateAsync(
                c => c.SetProperty(row => row.Label, shipClass.Label)
                    .SetProperty(row => row.MinSpeedKnots, shipClass.MinSpeedKnots)
                    .SetProperty(row => row.MaxSpeedKnots, shipClass.MaxSpeedKnots)
                    .SetProperty(row => row.TurnRadiusMeters, shipClass.TurnRadiusMeters)
                    .SetProperty(row => row.LengthMeters, shipClass.LengthMeters),
                cancellationToken)
            .ConfigureAwait(false) > 0;

    public async Task<IReadOnlyList<Ship>> ListShipsAsync(CancellationToken cancellationToken) =>
        await dbContext.Ships.AsNoTracking()
            .OrderBy(s => s.CallSign)
            .Select(s => new Ship(s.Id, s.CallSign, s.ClassCode, s.CreatedAt, s.RetiredAt))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

    public async Task<Ship?> FindShipAsync(Guid id, CancellationToken cancellationToken) =>
        await dbContext.Ships.AsNoTracking()
            .Where(s => s.Id == id)
            .Select(s => new Ship(s.Id, s.CallSign, s.ClassCode, s.CreatedAt, s.RetiredAt))
            .SingleOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

    public Task<bool> TryCreateShipAsync(Ship ship, CancellationToken cancellationToken)
    {
        dbContext.Ships.Add(new ShipRow { Id = ship.Id, CallSign = ship.CallSign, ClassCode = ship.ClassCode, CreatedAt = ship.CreatedAt });
        return TrySaveAsync(cancellationToken);
    }

    public async Task<bool> SetShipClassAsync(Guid id, string classCode, CancellationToken cancellationToken) =>
        await dbContext.Ships.Where(s => s.Id == id)
            .ExecuteUpdateAsync(s => s.SetProperty(row => row.ClassCode, classCode), cancellationToken)
            .ConfigureAwait(false) > 0;

    public async Task<bool> SetRetiredAtAsync(Guid id, DateTimeOffset? retiredAt, CancellationToken cancellationToken) =>
        await dbContext.Ships.Where(s => s.Id == id)
            .ExecuteUpdateAsync(s => s.SetProperty(row => row.RetiredAt, retiredAt), cancellationToken)
            .ConfigureAwait(false) > 0;

    private async Task<bool> TrySaveAsync(CancellationToken cancellationToken)
    {
        try
        {
            await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
            return true;
        }
        catch (DbUpdateException e) when (e.InnerException is PostgresException { SqlState: PostgresErrorCodes.UniqueViolation })
        {
            dbContext.ChangeTracker.Clear();
            return false;
        }
    }
}
