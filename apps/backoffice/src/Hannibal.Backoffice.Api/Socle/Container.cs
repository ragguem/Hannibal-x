using Hannibal.Backoffice.Application.Readiness;
using Hannibal.Backoffice.Domain;
using Hannibal.Backoffice.Infrastructure.Probes;
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
        return services;
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
