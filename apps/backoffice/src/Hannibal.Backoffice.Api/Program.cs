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

var app = builder.Build();
app.Services.GetRequiredService<BackofficeSettings>();
app.UseRequestId();
app.UseErrorBodies();
app.UseRouting();
app.UseHttpMetrics();
app.MapSystem();
await app.RunAsync().ConfigureAwait(false);

public partial class Program;
