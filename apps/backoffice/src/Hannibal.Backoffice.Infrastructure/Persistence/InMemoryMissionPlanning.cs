using System.Collections.Concurrent;
using Hannibal.Backoffice.Application.Planning;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

/// <summary>Mode <c>fake</c> : missions planifiées en mémoire, perdues à l'arrêt.</summary>
public sealed class InMemoryMissionPlanning : IMissionPlanning
{
    private readonly ConcurrentDictionary<Guid, PlannedMission> _missions = new();
    private readonly Lock _writes = new();

    public Task AddAsync(PlannedMission mission, CancellationToken cancellationToken)
    {
        _missions[mission.Id] = mission;
        return Task.CompletedTask;
    }

    public Task<PlannedMission?> FindAsync(Guid id, CancellationToken cancellationToken) => Task.FromResult(_missions.GetValueOrDefault(id));

    public Task<bool> TransitionAsync(Guid id, IReadOnlyCollection<string> from, string to, DateTimeOffset at, CancellationToken cancellationToken)
    {
        lock (_writes)
        {
            if (!_missions.TryGetValue(id, out var mission) || !from.Contains(mission.State))
            {
                return Task.FromResult(false);
            }
            _missions[id] = mission with
            {
                State = to,
                LaunchedAt = to == MissionState.Running ? at : mission.LaunchedAt,
                ArchivedAt = to == MissionState.Archived ? at : mission.ArchivedAt,
            };
            return Task.FromResult(true);
        }
    }

    public Task<IReadOnlyList<PlannedMission>> PageAsync(MissionCursor? after, int limit, CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<PlannedMission>>(
        [
            .. _missions.Values
                .OrderByDescending(m => m.CreatedAt).ThenByDescending(m => m.Id)
                .Where(m => after is null || m.CreatedAt < after.CreatedAt || (m.CreatedAt == after.CreatedAt && m.Id.CompareTo(after.Id) < 0))
                .Take(limit),
        ]);
}
