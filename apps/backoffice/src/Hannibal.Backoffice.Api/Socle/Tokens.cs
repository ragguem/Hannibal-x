using System.Security.Cryptography;
using System.Text;

namespace Hannibal.Backoffice.Api.Socle;

/// <summary>Jeton interne `X-Internal-Token` et jeton de collecte `/metrics`, mêmes règles que `hannibal_platform`.</summary>
public static class Tokens
{
    public const string InternalHeader = "X-Internal-Token";

    public static void RequireInternal(HttpContext context, BackofficeSettings settings) =>
        Require(settings.InternalToken, context.Request.Headers[InternalHeader].ToString(), settings.IsLocal, "jeton interne");

    public static void RequireMetrics(HttpContext context, BackofficeSettings settings)
    {
        var auth = context.Request.Headers.Authorization.ToString();
        var provided = auth.StartsWith("Bearer ", StringComparison.Ordinal) ? auth["Bearer ".Length..] : "";
        Require(settings.MetricsToken, provided, settings.IsLocal, "jeton de collecte");
    }

    /// <summary>Filtre de point d'accès pour les routes réservées aux services internes.</summary>
    public static TBuilder RequireInternalToken<TBuilder>(this TBuilder builder)
        where TBuilder : IEndpointConventionBuilder =>
        builder.AddEndpointFilter(async (invocation, next) =>
        {
            var settings = invocation.HttpContext.RequestServices.GetRequiredService<BackofficeSettings>();
            RequireInternal(invocation.HttpContext, settings);
            return await next(invocation).ConfigureAwait(false);
        });

    private static void Require(string? expected, string provided, bool isLocal, string label)
    {
        if (expected is null)
        {
            if (isLocal)
            {
                return;
            }
            throw new ForbiddenException($"{label} non configuré hors environnement local");
        }
        if (provided.Length == 0)
        {
            throw new UnauthenticatedException($"{label} absent");
        }
        if (!CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(provided), Encoding.UTF8.GetBytes(expected)))
        {
            throw new ForbiddenException($"{label} invalide");
        }
    }
}
