using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Infrastructure.Security;
using Hannibal.Backoffice.Infrastructure.Seeding;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;
using Hannibal.Backoffice.Infrastructure.Seeding.Seeders;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

/// <summary>Migrations EF Core (schéma seulement), puis seeders. Un échec de migration n'exécute aucun seeder.</summary>
public sealed class DatabaseInitializer(BackofficeDbContext dbContext, DataSeederOrchestrator orchestrator)
{
    public async Task InitializeAsync(CancellationToken cancellationToken)
    {
        await dbContext.Database.MigrateAsync(cancellationToken).ConfigureAwait(false);
        await orchestrator.SeedAllAsync(cancellationToken).ConfigureAwait(false);
    }
}

public static class IdentityPersistence
{
    public static IServiceCollection AddIdentityPersistence(
        this IServiceCollection services,
        Func<IServiceProvider, string> connectionString,
        Func<IServiceProvider, InitialAdminOptions> initialAdmin)
    {
        services.AddDbContext<BackofficeDbContext>((sp, builder) => BackofficeDbContext.Configure(builder, connectionString(sp)));
        services.AddSingleton<IPasswordHasher>(_ => new Argon2idPasswordHasher());
        services.AddSingleton(initialAdmin);
        services.AddScoped<IDataSeeder, RoleSeeder>();
        services.AddScoped<IDataSeeder, GameRoleSeeder>();
        services.AddScoped<IDataSeeder, InitialAdminSeeder>();
        services.AddScoped<DataSeederOrchestrator>();
        services.AddScoped<DatabaseInitializer>();
        return services;
    }
}
