using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

/// <summary>Premier compte administrateur, sans lequel personne ne peut se connecter.</summary>
public sealed record InitialAdminOptions(string Username, string? Password);

/// <summary>
/// Crée le compte de <see cref="InitialAdminOptions"/> s'il n'existe pas. Un compte n'est pas une donnée de
/// référence : s'il existe déjà, il n'est jamais modifié (mot de passe, rôle, désactivation).
/// Sans mot de passe fourni, rien n'est créé.
/// </summary>
public sealed class InitialAdminSeeder(
    BackofficeDbContext dbContext,
    IPasswordHasher passwordHasher,
    InitialAdminOptions options,
    ILogger<InitialAdminSeeder> logger) : IDataSeeder
{
    public int Order => 30;

    public string Name => nameof(InitialAdminSeeder);

    public async Task SeedAsync(CancellationToken cancellationToken)
    {
        if (options.Password is null)
        {
            logger.LogInformation("Aucun mot de passe d'administrateur initial fourni : compte non créé");
            return;
        }
        var exists = await dbContext.Users
            .AnyAsync(u => u.Username == options.Username, cancellationToken)
            .ConfigureAwait(false);
        if (exists)
        {
            return;
        }
        dbContext.Users.Add(new UserAccountRow
        {
            Id = Guid.CreateVersion7(),
            Username = options.Username,
            PasswordHash = passwordHasher.Hash(options.Password),
            RoleCode = RoleCode.Admin,
        });
        await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
        logger.LogInformation("Administrateur initial {Username} créé", options.Username);
    }
}
