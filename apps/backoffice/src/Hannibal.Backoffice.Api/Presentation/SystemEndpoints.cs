using Hannibal.Backoffice.Api.Socle;
using Hannibal.Backoffice.Application.Readiness;
using Hannibal.Backoffice.Domain;
using Prometheus;

namespace Hannibal.Backoffice.Api.Presentation;

public static class SystemEndpoints
{
    public static readonly string Version = typeof(SystemEndpoints).Assembly.GetName().Version?.ToString(3) ?? "0.0.0";

    public static IEndpointRouteBuilder MapSystem(this IEndpointRouteBuilder app)
    {
        var v1 = app.MapGroup("/v1").WithTags("santé");

        v1.MapGet("/health", () => new Health("ok", BackofficeSettings.ServiceName, Version));

        v1.MapGet("/ready", async (CheckReadiness check, CancellationToken ct) =>
        {
            var report = await check.ExecuteAsync(ct).ConfigureAwait(false);
            var body = new ReadinessBody(
                report.IsReady ? "ready" : "degraded",
                BackofficeSettings.ServiceName,
                Version,
                [.. report.Dependencies.Select(d => new DependencyStatusBody(d.Name, StateName(d.State), d.LatencyMs))]);
            return Results.Json(body, Json.Options, statusCode: report.IsReady ? StatusCodes.Status200OK : StatusCodes.Status503ServiceUnavailable);
        });

        app.MapGet("/metrics", async (HttpContext context, BackofficeSettings settings) =>
        {
            Tokens.RequireMetrics(context, settings);
            context.Response.ContentType = "text/plain; version=0.0.4; charset=utf-8";
            await Metrics.DefaultRegistry.CollectAndExportAsTextAsync(context.Response.Body, context.RequestAborted).ConfigureAwait(false);
        }).ExcludeFromDescription();

        return app;
    }

    private static string StateName(DependencyState state) => state switch
    {
        DependencyState.Up => "up",
        DependencyState.Down => "down",
        _ => "disabled",
    };
}
