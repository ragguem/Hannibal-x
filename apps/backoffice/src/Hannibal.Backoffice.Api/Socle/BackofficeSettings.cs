namespace Hannibal.Backoffice.Api.Socle;

public enum HxEnvironment
{
    Dev,
    Test,
    Integration,
    Production,
}

/// <summary>Variables `HX_BACKOFFICE_*`, mêmes noms et mêmes règles que `BaseServiceSettings` côté Python.</summary>
public sealed record BackofficeSettings
{
    public const string Prefix = "HX_BACKOFFICE_";
    public const string ServiceName = "backoffice";

    public HxEnvironment Environment { get; init; } = HxEnvironment.Dev;
    public string? InternalToken { get; init; }
    public string? MetricsToken { get; init; }
    public bool FakeAdapters { get; init; } = true;
    public string? DatabaseUrl { get; init; }
    public Uri? ApiUrl { get; init; }
    public TimeSpan ProbeTimeout { get; init; } = TimeSpan.FromSeconds(2);
    public string InitialAdminUsername { get; init; } = "admin";
    public string? InitialAdminPassword { get; init; }

    public bool IsLocal => Environment is HxEnvironment.Dev or HxEnvironment.Test;

    public static BackofficeSettings From(IConfiguration configuration)
    {
        string? Get(string key) => configuration[Prefix + key] is { Length: > 0 } value ? value : null;

        var adapters = Get("ADAPTERS") ?? "fake";
        if (adapters is not ("fake" or "real"))
        {
            throw new InvalidOperationException($"{Prefix}ADAPTERS doit valoir fake ou real, reçu « {adapters} »");
        }

        var settings = new BackofficeSettings
        {
            Environment = Enum.Parse<HxEnvironment>(Get("ENVIRONMENT") ?? "dev", ignoreCase: true),
            InternalToken = Get("INTERNAL_TOKEN"),
            MetricsToken = Get("METRICS_TOKEN"),
            FakeAdapters = adapters == "fake",
            DatabaseUrl = Get("DATABASE_URL"),
            ApiUrl = Get("API_URL") is { } url ? new Uri(url) : null,
            InitialAdminUsername = Get("INITIAL_ADMIN_USERNAME") ?? "admin",
            InitialAdminPassword = Get("INITIAL_ADMIN_PASSWORD"),
        };
        if (!settings.FakeAdapters && (settings.DatabaseUrl is null || settings.ApiUrl is null))
        {
            throw new InvalidOperationException($"{Prefix}DATABASE_URL et {Prefix}API_URL sont requis avec ADAPTERS=real");
        }
        return settings;
    }
}
