using Hannibal.Backoffice.Domain.Catalog;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;
using Microsoft.EntityFrameworkCore;

namespace Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

/// <summary>Navires de <see cref="ShipCatalogSeed.Ships"/>, ajoutés si absents. Clé : <c>call_sign</c>. Après <see cref="ShipClassSeeder"/>.</summary>
public sealed class ShipSeeder(BackofficeDbContext dbContext, TimeProvider clock) : IDataSeeder
{
    public int Order => 50;

    public string Name => nameof(ShipSeeder);

    public async Task SeedAsync(CancellationToken cancellationToken)
    {
        var existing = await dbContext.Ships.Select(s => s.CallSign).ToHashSetAsync(StringComparer.Ordinal, cancellationToken).ConfigureAwait(false);
        var missing = ShipCatalogSeed.Ships.Where(s => !existing.Contains(s.CallSign)).ToList();
        if (missing.Count == 0)
        {
            return;
        }
        var now = clock.GetUtcNow();
        dbContext.Ships.AddRange(missing.Select(s => new ShipRow { Id = Guid.CreateVersion7(), CallSign = s.CallSign, ClassCode = s.ClassCode, CreatedAt = now }));
        await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
    }
}
