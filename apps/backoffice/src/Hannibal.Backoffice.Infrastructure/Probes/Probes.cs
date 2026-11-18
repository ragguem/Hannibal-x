using System.Diagnostics;
using Hannibal.Backoffice.Application.Readiness;
using Hannibal.Backoffice.Domain;
using Npgsql;

namespace Hannibal.Backoffice.Infrastructure.Probes;

public sealed class PostgresProbe(NpgsqlDataSource dataSource, TimeSpan timeout) : IDependencyProbe
{
    public string Name => "postgres";

    public async Task<DependencyStatus> CheckAsync(CancellationToken cancellationToken)
    {
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        cts.CancelAfter(timeout);
        var started = Stopwatch.GetTimestamp();
        try
        {
            await using var command = dataSource.CreateCommand("SELECT 1");
            await command.ExecuteScalarAsync(cts.Token).ConfigureAwait(false);
            return new DependencyStatus(Name, DependencyState.Up, Stopwatch.GetElapsedTime(started).TotalMilliseconds);
        }
        catch (Exception e) when (e is NpgsqlException or OperationCanceledException or TimeoutException)
        {
            return new DependencyStatus(Name, DependencyState.Down);
        }
    }
}

public sealed class HttpHealthProbe(string name, HttpClient client, Uri healthUrl) : IDependencyProbe
{
    public string Name => name;

    public async Task<DependencyStatus> CheckAsync(CancellationToken cancellationToken)
    {
        var started = Stopwatch.GetTimestamp();
        try
        {
            using var response = await client.GetAsync(healthUrl, cancellationToken).ConfigureAwait(false);
            return response.IsSuccessStatusCode
                ? new DependencyStatus(Name, DependencyState.Up, Stopwatch.GetElapsedTime(started).TotalMilliseconds)
                : new DependencyStatus(Name, DependencyState.Down);
        }
        catch (Exception e) when (e is HttpRequestException or OperationCanceledException)
        {
            return new DependencyStatus(Name, DependencyState.Down);
        }
    }
}

public sealed class StaticProbe(string name, DependencyState state) : IDependencyProbe
{
    public string Name => name;

    public Task<DependencyStatus> CheckAsync(CancellationToken cancellationToken) =>
        Task.FromResult(new DependencyStatus(Name, state, state == DependencyState.Up ? 0 : null));
}
