using Hannibal.Backoffice.Api.Presentation;
using Hannibal.Backoffice.Api.Socle;
using Prometheus;

var builder = WebApplication.CreateBuilder(args);

builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole(o =>
{
    o.IncludeScopes = true;
    o.UseUtcTimestamp = true;
    o.TimestampFormat = "yyyy-MM-ddTHH:mm:ss.fffZ ";
});
builder.Services.ConfigureHttpJsonOptions(o => Json.Configure(o.SerializerOptions));
builder.Services.AddBackoffice();
builder.Services.AddOpenApi();

var app = builder.Build();
app.Services.GetRequiredService<BackofficeSettings>();
if (args.Contains("migratedb", StringComparer.Ordinal))
{
    await app.Services.InitializeDatabaseAsync(app.Lifetime.ApplicationStopping).ConfigureAwait(false);
    return;
}
app.UseRequestId();
app.UseErrorBodies();
app.UseRouting();
app.UseHttpMetrics();
app.UseAuthentication();
app.UseAuthorization();
app.MapSystem();
app.MapSession();
app.MapUsers();
app.MapOpenApi().AllowAnonymous();
app.MapReverseProxy();
await app.RunAsync().ConfigureAwait(false);

public partial class Program;
