using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;
using Microsoft.EntityFrameworkCore;

namespace Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

/// <summary>Rôles et permissions de <see cref="IdentityCatalog.Roles"/>. Clés : <c>code</c>, puis <c>(role_code, permission)</c>.</summary>
public sealed class RoleSeeder(BackofficeDbContext dbContext) : IDataSeeder
{
    public int Order => 10;

    public string Name => nameof(RoleSeeder);

    public async Task SeedAsync(CancellationToken cancellationToken)
    {
        var existingByCode = await dbContext.Roles
            .Include(r => r.Permissions)
            .ToDictionaryAsync(r => r.Code, StringComparer.Ordinal, cancellationToken)
            .ConfigureAwait(false);
        var changed = false;

        foreach (var definition in IdentityCatalog.Roles)
        {
            if (!existingByCode.TryGetValue(definition.Code, out var role))
            {
                role = new RoleRow { Code = definition.Code, Label = definition.Label };
                dbContext.Roles.Add(role);
                changed = true;
            }
            else if (role.Label != definition.Label)
            {
                role.Label = definition.Label;
                changed = true;
            }

            var granted = role.Permissions.Select(p => p.Permission).ToHashSet(StringComparer.Ordinal);
            foreach (var permission in definition.Permissions.Where(p => !granted.Contains(p)))
            {
                role.Permissions.Add(new RolePermissionRow { RoleCode = definition.Code, Permission = permission });
                changed = true;
            }
        }

        if (changed)
        {
            await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
        }
    }
}
