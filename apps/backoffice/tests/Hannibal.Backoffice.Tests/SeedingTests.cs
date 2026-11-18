using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Security;
using Hannibal.Backoffice.Infrastructure.Seeding;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;
using Hannibal.Backoffice.Infrastructure.Seeding.Seeders;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Npgsql;

namespace Hannibal.Backoffice.Tests;

/// <summary>
/// Migrations et seeders sur une base PostgreSQL jetable désignée par <c>HX_TEST_DATABASE_URL</c>
/// (même variable que les tests <c>-m postgres</c> de <c>apps/api</c>) ; ignorés sinon.
/// Le schéma <c>identity</c> est supprimé avant chaque test.
/// </summary>
public sealed class SeedingTests : IAsyncLifetime
{
    private static readonly Argon2idPasswordHasher Hasher = new(memoryKib: 1024, iterations: 1);
    private BackofficeDbContext _dbContext = null!;

    public async ValueTask InitializeAsync()
    {
        var url = Environment.GetEnvironmentVariable("HX_TEST_DATABASE_URL");
        Assert.SkipWhen(string.IsNullOrEmpty(url), "HX_TEST_DATABASE_URL non défini (base PostgreSQL jetable)");
        var builder = new DbContextOptionsBuilder<BackofficeDbContext>();
        BackofficeDbContext.Configure(builder, ToConnectionString(new Uri(url!)));
        _dbContext = new BackofficeDbContext(builder.Options);
        await _dbContext.Database.ExecuteSqlRawAsync($"DROP SCHEMA IF EXISTS {BackofficeDbContext.Schema} CASCADE", TestContext.Current.CancellationToken);
        await _dbContext.Database.MigrateAsync(TestContext.Current.CancellationToken);
    }

    public async ValueTask DisposeAsync()
    {
        if (_dbContext is not null)
        {
            await _dbContext.DisposeAsync();
        }
    }

    private static string ToConnectionString(Uri url)
    {
        var credentials = url.UserInfo.Split(':', 2);
        return new NpgsqlConnectionStringBuilder
        {
            Host = url.Host,
            Port = url.Port,
            Database = url.AbsolutePath.TrimStart('/'),
            Username = Uri.UnescapeDataString(credentials[0]),
            Password = Uri.UnescapeDataString(credentials[1]),
        }.ConnectionString;
    }

    private DataSeederOrchestrator Orchestrator(string? adminPassword = "mot-de-passe-initial", params IDataSeeder[] extra) =>
        new(
            [
                new RoleSeeder(_dbContext),
                new GameRoleSeeder(_dbContext),
                new InitialAdminSeeder(_dbContext, Hasher, new InitialAdminOptions("admin", adminPassword), NullLogger<InitialAdminSeeder>.Instance),
                .. extra,
            ],
            _dbContext,
            NullLogger<DataSeederOrchestrator>.Instance);

    private async Task<Dictionary<string, string[]>> PermissionsByRoleAsync() =>
        await _dbContext.RolePermissions.AsNoTracking()
            .GroupBy(p => p.RoleCode)
            .ToDictionaryAsync(g => g.Key, g => g.Select(p => p.Permission).Order().ToArray(), TestContext.Current.CancellationToken);

    [Fact]
    public async Task Le_seed_cree_les_donnees_de_reference_et_reste_idempotent()
    {
        await Orchestrator().SeedAllAsync(TestContext.Current.CancellationToken);
        var hashAfterFirstRun = await _dbContext.Users.AsNoTracking().Select(u => u.PasswordHash).SingleAsync(TestContext.Current.CancellationToken);
        _dbContext.ChangeTracker.Clear();
        await Orchestrator(adminPassword: "autre-mot-de-passe").SeedAllAsync(TestContext.Current.CancellationToken);

        var permissions = await PermissionsByRoleAsync();
        foreach (var role in IdentityCatalog.Roles)
        {
            Assert.Equal(role.Permissions.Order(), permissions[role.Code]);
        }
        Assert.Equal(["escort", "guide"], await _dbContext.GameRoles.Select(g => g.Code).Order().ToListAsync(TestContext.Current.CancellationToken));
        var admin = await _dbContext.Users.AsNoTracking().SingleAsync(TestContext.Current.CancellationToken);
        Assert.Equal((RoleCode.Admin, hashAfterFirstRun), (admin.RoleCode, admin.PasswordHash));
        Assert.True(Hasher.Verify("mot-de-passe-initial", admin.PasswordHash));
    }

    [Fact]
    public async Task Le_seed_realigne_une_donnee_modifiee_sans_supprimer_les_ajouts()
    {
        await Orchestrator().SeedAllAsync(TestContext.Current.CancellationToken);
        await _dbContext.Database.ExecuteSqlRawAsync(
            "UPDATE identity.roles SET label = 'modifié'; INSERT INTO identity.game_roles VALUES ('observer', 'Observateur', 'ajout local')",
            TestContext.Current.CancellationToken);
        _dbContext.ChangeTracker.Clear();

        await Orchestrator().SeedAllAsync(TestContext.Current.CancellationToken);

        var labels = await _dbContext.Roles.AsNoTracking().ToDictionaryAsync(r => r.Code, r => r.Label, TestContext.Current.CancellationToken);
        Assert.Equal(IdentityCatalog.Roles.ToDictionary(r => r.Code, r => r.Label), labels);
        Assert.True(await _dbContext.GameRoles.AnyAsync(g => g.Code == "observer", TestContext.Current.CancellationToken));
    }

    [Fact]
    public async Task Un_seeder_en_echec_est_annule_sans_priver_les_suivants()
    {
        var failure = await Assert.ThrowsAsync<AggregateException>(
            () => Orchestrator(null, new FailingSeeder(_dbContext)).SeedAllAsync(TestContext.Current.CancellationToken));

        Assert.Contains("FailingSeeder", Assert.Single(failure.InnerExceptions).Message, StringComparison.Ordinal);
        Assert.False(await _dbContext.Roles.AnyAsync(r => r.Code == "partial", TestContext.Current.CancellationToken));
        Assert.Equal(2, await _dbContext.GameRoles.CountAsync(TestContext.Current.CancellationToken));
        Assert.False(await _dbContext.Users.AnyAsync(TestContext.Current.CancellationToken));
    }

    /// <summary>Écrit une ligne, puis échoue : la ligne ne doit pas survivre (ordre 15, entre rôles et rôles de jeu).</summary>
    private sealed class FailingSeeder(BackofficeDbContext dbContext) : IDataSeeder
    {
        public int Order => 15;

        public string Name => nameof(FailingSeeder);

        public async Task SeedAsync(CancellationToken cancellationToken)
        {
            dbContext.Roles.Add(new RoleRow { Code = "partial", Label = "écrit puis annulé" });
            await dbContext.SaveChangesAsync(cancellationToken);
            throw new InvalidOperationException("panne simulée");
        }
    }
}
