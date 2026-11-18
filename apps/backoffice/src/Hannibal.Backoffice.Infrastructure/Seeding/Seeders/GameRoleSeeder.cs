using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;
using Microsoft.EntityFrameworkCore;

namespace Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

/// <summary>Rôles de jeu de <see cref="IdentityCatalog.GameRoles"/>. Clé : <c>code</c>.</summary>
public sealed class GameRoleSeeder(BackofficeDbContext dbContext) : IDataSeeder
{
    public int Order => 20;

    public string Name => nameof(GameRoleSeeder);

    public async Task SeedAsync(CancellationToken cancellationToken)
    {
        var existingByCode = await dbContext.GameRoles
            .ToDictionaryAsync(g => g.Code, StringComparer.Ordinal, cancellationToken)
            .ConfigureAwait(false);
        var changed = false;

        foreach (var definition in IdentityCatalog.GameRoles)
        {
            if (!existingByCode.TryGetValue(definition.Code, out var gameRole))
            {
                dbContext.GameRoles.Add(new GameRoleRow { Code = definition.Code, Label = definition.Label, Description = definition.Description });
                changed = true;
            }
            else if (gameRole.Label != definition.Label || gameRole.Description != definition.Description)
            {
                gameRole.Label = definition.Label;
                gameRole.Description = definition.Description;
                changed = true;
            }
        }

        if (changed)
        {
            await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
        }
    }
}
