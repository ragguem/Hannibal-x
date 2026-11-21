using Hannibal.Backoffice.Application.Planning;
using Npgsql;

namespace Hannibal.Backoffice.Infrastructure.Planning;

/// <summary>
/// Lit <c>ops_read.mission_runs</c>, vue publiée par <c>apps/api</c>. Tant qu'<c>apps/api</c> n'a pas migré sa base,
/// la vue n'existe pas : l'historique montre alors les missions sans leur déroulé.
/// </summary>
public sealed class PostgresMissionRuns(NpgsqlDataSource dataSource) : IMissionRuns
{
    public async Task<IReadOnlyDictionary<Guid, MissionRunSummary>> FindAsync(IReadOnlyCollection<Guid> missionIds, CancellationToken cancellationToken)
    {
        var runs = new Dictionary<Guid, MissionRunSummary>();
        if (missionIds.Count == 0)
        {
            return runs;
        }
        var command = dataSource.CreateCommand(
            "SELECT mission_id, phase, started_at, finished_at FROM ops_read.mission_runs WHERE mission_id = ANY(@ids)");
        await using (command.ConfigureAwait(false))
        {
            command.Parameters.AddWithValue("ids", missionIds.ToArray());
            try
            {
                var reader = await command.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
                await using (reader.ConfigureAwait(false))
                {
                    while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
                    {
                        var id = reader.GetGuid(0);
                        runs[id] = new MissionRunSummary(
                            id,
                            reader.GetString(1),
                            reader.GetFieldValue<DateTimeOffset>(2),
                            reader.IsDBNull(3) ? null : reader.GetFieldValue<DateTimeOffset>(3));
                    }
                }
            }
            catch (PostgresException e) when (e.SqlState is PostgresErrorCodes.UndefinedTable or PostgresErrorCodes.InvalidSchemaName)
            {
                return runs;
            }
        }
        return runs;
    }
}
