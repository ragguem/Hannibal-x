using System.Collections.Concurrent;
using Hannibal.Backoffice.Application.Planning;

namespace Hannibal.Backoffice.Infrastructure.Planning;

/// <summary>Mode <c>fake</c> : <c>apps/api</c> simulé ; garde les photos reçues et répond comme elle, sans rien jouer.</summary>
public sealed class InMemoryMissionRunner(TimeProvider time) : IMissionLauncher, IMissionRuns
{
    private readonly ConcurrentDictionary<Guid, (MissionSnapshot Snapshot, MissionRunSummary Run)> _runs = new();

    public IReadOnlyDictionary<Guid, MissionSnapshot> Snapshots => _runs.ToDictionary(r => r.Key, r => r.Value.Snapshot);

    public Task LaunchAsync(Guid missionId, MissionSnapshot snapshot, CancellationToken cancellationToken)
    {
        _runs.TryAdd(missionId, (snapshot, new MissionRunSummary(missionId, "running", time.GetUtcNow(), null)));
        return Task.CompletedTask;
    }

    public void Finish(Guid missionId) =>
        _runs[missionId] = _runs[missionId] with { Run = _runs[missionId].Run with { Phase = "finished", FinishedAt = time.GetUtcNow() } };

    public Task<IReadOnlyDictionary<Guid, MissionRunSummary>> FindAsync(IReadOnlyCollection<Guid> missionIds, CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyDictionary<Guid, MissionRunSummary>>(
            missionIds.Where(_runs.ContainsKey).ToDictionary(id => id, id => _runs[id].Run));
}
