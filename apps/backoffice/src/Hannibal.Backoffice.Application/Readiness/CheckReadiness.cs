using Hannibal.Backoffice.Domain;

namespace Hannibal.Backoffice.Application.Readiness;

public interface IDependencyProbe
{
    string Name { get; }

    Task<DependencyStatus> CheckAsync(CancellationToken cancellationToken);
}

public sealed class CheckReadiness(IEnumerable<IDependencyProbe> probes)
{
    public async Task<ReadinessReport> ExecuteAsync(CancellationToken cancellationToken)
    {
        var statuses = await Task.WhenAll(probes.Select(p => p.CheckAsync(cancellationToken))).ConfigureAwait(false);
        return new ReadinessReport(statuses);
    }
}
