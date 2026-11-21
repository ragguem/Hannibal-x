using Hannibal.Backoffice.Application.Planning;
using Microsoft.EntityFrameworkCore;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

public sealed class EfMissionPlanning(BackofficeDbContext dbContext) : IMissionPlanning
{
    public async Task AddAsync(PlannedMission mission, CancellationToken cancellationToken)
    {
        dbContext.Missions.Add(new MissionRow
        {
            Id = mission.Id,
            ScenarioId = mission.ScenarioId,
            ScenarioVersion = mission.ScenarioVersion,
            PlayerShipId = mission.PlayerShipId,
            Autopilot = mission.Autopilot,
            ManualHelm = mission.ManualHelm,
            State = mission.State,
            PlannedBy = mission.PlannedBy,
            CreatedAt = mission.CreatedAt,
            Participants = [.. mission.Participants.Select(p => new MissionParticipantRow
            {
                MissionId = mission.Id,
                ShipId = p.ShipId,
                UserId = p.UserId,
                GameRoleCode = p.GameRole,
            })],
        });
        await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
        dbContext.ChangeTracker.Clear();
    }

    public async Task<PlannedMission?> FindAsync(Guid id, CancellationToken cancellationToken) =>
        await Rows().Where(m => m.Id == id).SingleOrDefaultAsync(cancellationToken).ConfigureAwait(false) is { } row ? ToMission(row) : null;

    public async Task<bool> TransitionAsync(Guid id, IReadOnlyCollection<string> from, string to, DateTimeOffset at, CancellationToken cancellationToken) =>
        await dbContext.Missions.Where(m => m.Id == id && from.Contains(m.State))
            .ExecuteUpdateAsync(
                m => m.SetProperty(row => row.State, to)
                    .SetProperty(row => row.LaunchedAt, row => to == MissionState.Running ? at : row.LaunchedAt)
                    .SetProperty(row => row.ArchivedAt, row => to == MissionState.Archived ? at : row.ArchivedAt),
                cancellationToken)
            .ConfigureAwait(false) > 0;

    public async Task<IReadOnlyList<PlannedMission>> PageAsync(MissionCursor? after, int limit, CancellationToken cancellationToken)
    {
        var query = Rows();
        if (after is not null)
        {
            query = query.Where(m => m.CreatedAt < after.CreatedAt);
        }
        var rows = await query.OrderByDescending(m => m.CreatedAt).ThenByDescending(m => m.Id).Take(limit)
            .ToListAsync(cancellationToken).ConfigureAwait(false);
        return [.. rows.Select(ToMission)];
    }

    private IQueryable<MissionRow> Rows() => dbContext.Missions.AsNoTracking().Include(m => m.Participants);

    private static PlannedMission ToMission(MissionRow row) => new(
        row.Id,
        row.ScenarioId,
        row.ScenarioVersion,
        row.PlayerShipId,
        row.Autopilot,
        row.ManualHelm,
        row.State,
        row.PlannedBy,
        row.CreatedAt,
        row.LaunchedAt,
        row.ArchivedAt,
        [.. row.Participants.Select(p => new Participant(p.UserId, p.ShipId, p.GameRoleCode))]);
}
