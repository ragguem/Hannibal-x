using Hannibal.Backoffice.Application.Catalog;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

public sealed class EfScenarioCatalog(BackofficeDbContext dbContext) : IScenarioCatalog
{
    public async Task<IReadOnlyList<ScenarioEntry>> ListAsync(CancellationToken cancellationToken) =>
        await Entries().OrderBy(e => e.Id).ToListAsync(cancellationToken).ConfigureAwait(false);

    public async Task<ScenarioEntry?> FindAsync(string id, CancellationToken cancellationToken) =>
        await Entries().Where(e => e.Id == id).SingleOrDefaultAsync(cancellationToken).ConfigureAwait(false);

    public async Task<bool> TryAddVersionAsync(NewScenarioVersion version, CancellationToken cancellationToken)
    {
        var document = version.Document;
        var scenario = await dbContext.Scenarios.SingleOrDefaultAsync(s => s.Id == document.Id, cancellationToken).ConfigureAwait(false);
        if (scenario is null)
        {
            dbContext.Scenarios.Add(new ScenarioRow { Id = document.Id, Title = document.Title, Level = document.Level, CreatedAt = version.ImportedAt });
        }
        else
        {
            scenario.Title = document.Title;
            scenario.Level = document.Level;
        }
        dbContext.ScenarioVersions.Add(new ScenarioVersionRow
        {
            ScenarioId = document.Id,
            Version = version.Version,
            Document = document.Json,
            ContentSha256 = document.ContentSha256,
            Source = version.Source,
            ImportedBy = version.ImportedBy,
            ImportedAt = version.ImportedAt,
        });
        try
        {
            await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
            return true;
        }
        catch (DbUpdateException e) when (e.InnerException is PostgresException { SqlState: PostgresErrorCodes.UniqueViolation })
        {
            dbContext.ChangeTracker.Clear();
            return false;
        }
    }

    public async Task<bool> SetPublishedVersionAsync(string id, int version, CancellationToken cancellationToken) =>
        await dbContext.Scenarios.Where(s => s.Id == id)
            .ExecuteUpdateAsync(s => s.SetProperty(row => row.PublishedVersion, version), cancellationToken)
            .ConfigureAwait(false) > 0;

    public async Task<bool> SetArchivedAtAsync(string id, DateTimeOffset archivedAt, CancellationToken cancellationToken) =>
        await dbContext.Scenarios.Where(s => s.Id == id)
            .ExecuteUpdateAsync(s => s.SetProperty(row => row.ArchivedAt, archivedAt), cancellationToken)
            .ConfigureAwait(false) > 0;

    public async Task<string?> SourceOfAsync(string id, int version, CancellationToken cancellationToken) =>
        await dbContext.ScenarioVersions.AsNoTracking()
            .Where(v => v.ScenarioId == id && v.Version == version)
            .Select(v => v.Source)
            .SingleOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

    public async Task<string?> DocumentOfAsync(string id, int version, CancellationToken cancellationToken) =>
        await dbContext.ScenarioVersions.AsNoTracking()
            .Where(v => v.ScenarioId == id && v.Version == version)
            .Select(v => v.Document)
            .SingleOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

    private IQueryable<ScenarioEntry> Entries() =>
        from s in dbContext.Scenarios.AsNoTracking()
        let latest = dbContext.ScenarioVersions.Where(v => v.ScenarioId == s.Id).OrderByDescending(v => v.Version).First()
        select new ScenarioEntry(s.Id, s.Title, s.Level, s.PublishedVersion, latest.Version, latest.ContentSha256, s.ArchivedAt);
}
