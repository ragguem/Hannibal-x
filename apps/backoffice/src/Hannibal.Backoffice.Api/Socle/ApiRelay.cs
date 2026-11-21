using System.Security.Claims;
using Hannibal.Backoffice.Domain.Identity;
using Yarp.ReverseProxy.Configuration;
using Yarp.ReverseProxy.Transforms;

namespace Hannibal.Backoffice.Api.Socle;

/// <summary>
/// Relais YARP vers <c>apps/api</c> (ADR 0007). Chaque route exige une permission ; l'identité transmise est celle
/// de la session, jamais un en-tête du navigateur. Le cookie de session ne quitte pas le back-office.
/// </summary>
public static class ApiRelay
{
    public const string UserHeader = "X-Hx-User";
    public const string PermissionsHeader = "X-Hx-Permissions";
    private const string ClusterId = "api";

    /// <summary>Routes relayées : (identifiant, motif, méthodes, permission). Les motifs précis passent devant.</summary>
    public static readonly IReadOnlyList<(string Id, string Path, string[]? Methods, string Permission)> Routes =
    [
        ("orders", "/v1/missions/{missionId}/orders", ["POST"], Permission.CommandSubmit),
        ("voice", "/v1/missions/{missionId}/voice", ["POST"], Permission.CommandSubmit),
        ("simulations", "/v1/missions/{missionId}/simulations", ["POST"], Permission.CommandSubmit),
        ("request-reply", "/v1/missions/{missionId}/requests/{ship}/reply", ["POST"], Permission.CommandDecide),
        ("missions", "/v1/missions/{**rest}", null, Permission.MissionPlay),
        ("command-decision", "/v1/commands/{commandId}/decision", ["POST"], Permission.CommandDecide),
        ("command-explanation", "/v1/commands/{commandId}/explanation", ["POST"], Permission.DoctrineAsk),
        ("doctrine", "/v1/doctrine/{**rest}", ["GET", "POST"], Permission.DoctrineAsk),
        ("glossary", "/v1/glossary", ["GET"], Permission.GlossaryRead),
        ("commands", "/v1/commands/{commandId}", ["GET"], Permission.MissionPlay),
        ("audit", "/v1/audit/{**rest}", ["GET"], Permission.AuditRead),
    ];

    public static IServiceCollection AddApiRelay(this IServiceCollection services, Func<IServiceProvider, Uri> apiUrl)
    {
        services.AddReverseProxy()
            .AddTransforms(context =>
            {
                context.RequestTransforms.Add(new RequestHeaderRemoveTransform("Cookie"));
                context.RequestTransforms.Add(new RequestHeaderRemoveTransform(UserHeader));
                context.RequestTransforms.Add(new RequestHeaderRemoveTransform(PermissionsHeader));
                context.RequestTransforms.Add(new RequestHeaderRemoveTransform(Tokens.InternalHeader));
                context.AddRequestTransform(transform =>
                {
                    var http = transform.HttpContext;
                    transform.ProxyRequest.Headers.TryAddWithoutValidation(UserHeader, http.User.FindFirstValue(ClaimTypes.Name));
                    var permissions = http.User.FindAll(SessionAuthentication.PermissionClaim).Select(c => c.Value);
                    transform.ProxyRequest.Headers.TryAddWithoutValidation(PermissionsHeader, string.Join(',', permissions));
                    if (http.RequestServices.GetRequiredService<BackofficeSettings>().InternalToken is { } token)
                    {
                        transform.ProxyRequest.Headers.TryAddWithoutValidation(Tokens.InternalHeader, token);
                    }
                    return ValueTask.CompletedTask;
                });
            });
        services.AddSingleton<IProxyConfigProvider>(sp => new RelayConfig(apiUrl(sp)));
        return services;
    }

    private sealed class RelayConfig(Uri apiUrl) : IProxyConfigProvider
    {
        private readonly IProxyConfig _config = new Config(
            [
                .. Routes.Select((route, index) => new RouteConfig
                {
                    RouteId = route.Id,
                    ClusterId = ClusterId,
                    Order = index,
                    AuthorizationPolicy = route.Permission,
                    Match = new RouteMatch { Path = route.Path, Methods = route.Methods },
                }),
            ],
            [
                new ClusterConfig
                {
                    ClusterId = ClusterId,
                    Destinations = new Dictionary<string, DestinationConfig>(StringComparer.Ordinal)
                    {
                        ["api"] = new() { Address = apiUrl.ToString() },
                    },
                },
            ]);

        public IProxyConfig GetConfig() => _config;
    }

    private sealed class Config(IReadOnlyList<RouteConfig> routes, IReadOnlyList<ClusterConfig> clusters) : IProxyConfig
    {
        public IReadOnlyList<RouteConfig> Routes { get; } = routes;
        public IReadOnlyList<ClusterConfig> Clusters { get; } = clusters;
        public Microsoft.Extensions.Primitives.IChangeToken ChangeToken { get; } = new Microsoft.Extensions.Primitives.CancellationChangeToken(CancellationToken.None);
    }
}
