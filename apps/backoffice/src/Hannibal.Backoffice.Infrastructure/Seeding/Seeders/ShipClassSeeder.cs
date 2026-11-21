using Hannibal.Backoffice.Domain.Catalog;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;
using Microsoft.EntityFrameworkCore;

namespace Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

/// <summary>Classes de <see cref="ShipCatalogSeed.Classes"/>, ajoutées si absentes. Clé : <c>code</c>. Une classe modifiée par l'administrateur n'est pas écrasée.</summary>
public sealed class ShipClassSeeder(BackofficeDbContext dbContext) : IDataSeeder
{
    public int Order => 40;

    public string Name => nameof(ShipClassSeeder);

    public async Task SeedAsync(CancellationToken cancellationToken)
    {
        var existing = await dbContext.ShipClasses.Select(c => c.Code).ToHashSetAsync(StringComparer.Ordinal, cancellationToken).ConfigureAwait(false);
        var missing = ShipCatalogSeed.Classes.Where(c => !existing.Contains(c.Code)).ToList();
        if (missing.Count == 0)
        {
            return;
        }
        dbContext.ShipClasses.AddRange(missing.Select(c => new ShipClassRow
        {
            Code = c.Code,
            Label = c.Label,
            MinSpeedKnots = c.MinSpeedKnots,
            MaxSpeedKnots = c.MaxSpeedKnots,
            TurnRadiusMeters = c.TurnRadiusMeters,
            LengthMeters = c.LengthMeters,
        }));
        await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
    }
}
