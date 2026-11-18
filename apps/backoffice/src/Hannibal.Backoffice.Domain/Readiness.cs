namespace Hannibal.Backoffice.Domain;

public enum DependencyState
{
    Up,
    Down,
    Disabled,
}

public sealed record DependencyStatus(string Name, DependencyState State, double? LatencyMs = null);

public sealed record ReadinessReport(IReadOnlyList<DependencyStatus> Dependencies)
{
    public bool IsReady => Dependencies.All(d => d.State != DependencyState.Down);
}
