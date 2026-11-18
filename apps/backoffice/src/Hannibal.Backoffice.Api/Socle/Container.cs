using Hannibal.Backoffice.Application.Readiness;
using Hannibal.Backoffice.Domain;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Probes;
using Hannibal.Backoffice.Infrastructure.Seeding.Seeders;
using Npgsql;

namespace Hannibal.Backoffice.Api.Socle;

/// <summary>Composition : adaptateurs faux (`HX_BACKOFFICE_ADAPTERS=fake`) ou réels, choisis à la résolution.</summary>
public static class Container
{
    public static IServiceCollection AddBackoffice(this IServiceCollection services)
    {
        services.AddSingleton(sp => BackofficeSettings.From(sp.GetRequiredService<IConfiguration>()));
        services.AddHttpClient("api");
        services.AddSingleton(sp => NpgsqlDataSource.Create(Settings(sp).DatabaseUrl!));
        services.AddSingleton(sp => new CheckReadiness(Probes(sp)));
        services.AddIdentityPersistence(
            sp => Settings(sp).DatabaseUrl ?? throw new InvalidOperationException($"{BackofficeSettings.Prefix}DATABASE_URL non défini"),
            sp => new InitialAdminOptions(Settings(sp).InitialAdminUsername, Settings(sp).InitialAdminPassword));
        return services;
    }

    /// <summary>
    /// Mode <c>migratedb</c> : migrations puis seeders, puis arrêt. Pas au démarrage du serveur, qui doit
    /// démarrer et se dire dégradé si la base ne répond pas. Mode faux : aucune base, rien à faire.
    /// </summary>
    public static async Task InitializeDatabaseAsync(this IServiceProvider services, CancellationToken cancellationToken)
    {
        if (Settings(services).FakeAdapters)
        {
            return;
        }
        var scope = services.CreateAsyncScope();
        await using (scope.ConfigureAwait(false))
        {
            await scope.ServiceProvider.GetRequiredService<DatabaseInitializer>().InitializeAsync(cancellationToken).ConfigureAwait(false);
        }
    }

    private static BackofficeSettings Settings(IServiceProvider sp) => sp.GetRequiredService<BackofficeSettings>();

    private static IDependencyProbe[] Probes(IServiceProvider sp)
    {
        var settings = Settings(sp);
        if (settings.FakeAdapters)
        {
            return [new StaticProbe("postgres", DependencyState.Up), new StaticProbe("api", DependencyState.Up)];
        }
        var client = sp.GetRequiredService<IHttpClientFactory>().CreateClient("api");
        client.Timeout = settings.ProbeTimeout;
        return
        [
            new PostgresProbe(sp.GetRequiredService<NpgsqlDataSource>(), settings.ProbeTimeout),
            new HttpHealthProbe("api", client, new Uri(settings.ApiUrl!, "/v1/health")),
        ];
    }
}
