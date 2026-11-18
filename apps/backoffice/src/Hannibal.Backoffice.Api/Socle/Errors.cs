using System.Text.RegularExpressions;
using Microsoft.AspNetCore.WebUtilities;

namespace Hannibal.Backoffice.Api.Socle;

public abstract class ApiException(string detail) : Exception(detail)
{
    public abstract int Status { get; }
    public abstract string Code { get; }
    public abstract string PublicMessage { get; }
}

public sealed class UnauthenticatedException(string detail) : ApiException(detail)
{
    public override int Status => StatusCodes.Status401Unauthorized;
    public override string Code => "unauthenticated";
    public override string PublicMessage => "Authentification requise.";
}

public sealed class ForbiddenException(string detail) : ApiException(detail)
{
    public override int Status => StatusCodes.Status403Forbidden;
    public override string Code => "forbidden";
    public override string PublicMessage => "Action non autorisée.";
}

public static partial class RequestIds
{
    public const string Header = "x-request-id";
    private const string ItemKey = "hx.request_id";

    [GeneratedRegex("^[A-Za-z0-9._-]{8,64}$")]
    private static partial Regex Accepted();

    public static string? Of(HttpContext context) => context.Items[ItemKey] as string;

    /// <summary>Lit `X-Request-Id` ou en crée un, l'ajoute à la portée de journal et le renvoie dans la réponse.</summary>
    public static IApplicationBuilder UseRequestId(this IApplicationBuilder app) =>
        app.Use(async (context, next) =>
        {
            var incoming = context.Request.Headers[Header].ToString();
            var requestId = Accepted().IsMatch(incoming) ? incoming : Guid.NewGuid().ToString("N");
            context.Items[ItemKey] = requestId;
            context.Response.Headers[Header] = requestId;
            var logger = context.RequestServices.GetRequiredService<ILoggerFactory>().CreateLogger("hx.request");
            using (logger.BeginScope("request_id={request_id}", requestId))
            {
                await next(context).ConfigureAwait(false);
            }
        });
}

public static class ErrorHandling
{
    /// <summary>Traduit toute erreur en `ErrorBody`, comme `hannibal_platform.errors`.</summary>
    public static IApplicationBuilder UseErrorBodies(this IApplicationBuilder app)
    {
        app.Use(async (context, next) =>
        {
            try
            {
                await next(context).ConfigureAwait(false);
            }
            catch (ApiException e)
            {
                Log(context).LogWarning("request_failed code={Code} detail={Detail}", e.Code, e.Message);
                await Write(context, e.Status, new ErrorBody(e.Code, e.PublicMessage, RequestIds.Of(context))).ConfigureAwait(false);
            }
#pragma warning disable CA1031 // dernier filet : aucune exception ne sort sans ErrorBody
            catch (Exception e) when (!context.Response.HasStarted)
#pragma warning restore CA1031
            {
                Log(context).LogError(e, "unhandled_error");
                await Write(context, StatusCodes.Status500InternalServerError, new ErrorBody("internal", "Erreur interne.", RequestIds.Of(context))).ConfigureAwait(false);
            }
        });
        app.UseStatusCodePages(async status =>
        {
            var context = status.HttpContext;
            var phrase = ReasonPhrases.GetReasonPhrase(context.Response.StatusCode);
            await Write(context, context.Response.StatusCode, new ErrorBody("http_error", phrase, RequestIds.Of(context))).ConfigureAwait(false);
        });
        return app;
    }

    private static ILogger Log(HttpContext context) =>
        context.RequestServices.GetRequiredService<ILoggerFactory>().CreateLogger("hx.errors");

    private static Task Write(HttpContext context, int status, ErrorBody body)
    {
        context.Response.StatusCode = status;
        return context.Response.WriteAsJsonAsync(body, Json.Options);
    }
}
