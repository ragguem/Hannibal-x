namespace Hannibal.Backoffice.Application.Catalog;

/// <summary>
/// Scénarios du catalogue (Lot 7.4). Chaque import différent du dernier crée une version ; une seule version est
/// publiée, c'est elle que la planification proposera. Un scénario archivé ne change plus.
/// </summary>
public sealed class Scenarios(IScenarioCatalog catalog, IScenarioDocuments documents, IShipCatalog ships, TimeProvider clock)
{
    public Task<IReadOnlyList<ScenarioEntry>> ListAsync(CancellationToken cancellationToken) => catalog.ListAsync(cancellationToken);

    /// <summary>Un import identique à la dernière version la renvoie sans en créer une nouvelle.</summary>
    public async Task<ScenarioEntry> ImportAsync(string yaml, Guid? importedBy, CancellationToken cancellationToken)
    {
        var document = documents.Parse(yaml);
        await RequireActiveFleetAsync(document, cancellationToken).ConfigureAwait(false);
        var existing = await catalog.FindAsync(document.Id, cancellationToken).ConfigureAwait(false);
        if (existing?.ArchivedAt is not null)
        {
            throw new RuleViolation(RuleKind.Conflict, "scénario archivé", $"Le scénario « {document.Id} » est archivé.");
        }
        if (existing?.LatestSha256 == document.ContentSha256)
        {
            return existing;
        }
        var version = new NewScenarioVersion(document, (existing?.LatestVersion ?? 0) + 1, yaml, importedBy, clock.GetUtcNow());
        if (!await catalog.TryAddVersionAsync(version, cancellationToken).ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.Conflict, "version importée en parallèle");
        }
        return await RequireAsync(document.Id, cancellationToken).ConfigureAwait(false);
    }

    public async Task<ScenarioEntry> PublishAsync(string id, int version, CancellationToken cancellationToken)
    {
        var entry = await RequireAsync(id, cancellationToken).ConfigureAwait(false);
        if (entry.ArchivedAt is not null)
        {
            throw new RuleViolation(RuleKind.Conflict, "scénario archivé");
        }
        if (version < 1 || version > entry.LatestVersion)
        {
            throw new RuleViolation(RuleKind.Invalid, "version inconnue");
        }
        await catalog.SetPublishedVersionAsync(id, version, cancellationToken).ConfigureAwait(false);
        return await RequireAsync(id, cancellationToken).ConfigureAwait(false);
    }

    public async Task<ScenarioEntry> ArchiveAsync(string id, CancellationToken cancellationToken)
    {
        if (!await catalog.SetArchivedAtAsync(id, clock.GetUtcNow(), cancellationToken).ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.NotFound, "scénario inconnu");
        }
        return await RequireAsync(id, cancellationToken).ConfigureAwait(false);
    }

    public async Task<string> ExportAsync(string id, int version, CancellationToken cancellationToken) =>
        await catalog.SourceOfAsync(id, version, cancellationToken).ConfigureAwait(false)
        ?? throw new RuleViolation(RuleKind.NotFound, "version inconnue");

    private async Task RequireActiveFleetAsync(ParsedScenario document, CancellationToken cancellationToken)
    {
        var active = (await ships.ListShipsAsync(cancellationToken).ConfigureAwait(false))
            .Where(s => s.RetiredAt is null)
            .Select(s => s.CallSign)
            .ToHashSet(StringComparer.Ordinal);
        var missing = document.Fleet.Where(callSign => !active.Contains(callSign)).ToList();
        if (missing.Count > 0)
        {
            throw new RuleViolation(
                RuleKind.Invalid,
                "flotte hors catalogue",
                $"Navires absents du catalogue ou retirés : {string.Join(", ", missing)}.");
        }
    }

    private async Task<ScenarioEntry> RequireAsync(string id, CancellationToken cancellationToken) =>
        await catalog.FindAsync(id, cancellationToken).ConfigureAwait(false)
        ?? throw new RuleViolation(RuleKind.NotFound, "scénario inconnu");
}
