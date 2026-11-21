using System.Collections.Concurrent;
using Hannibal.Backoffice.Application.Catalog;
using Hannibal.Backoffice.Infrastructure.Catalog;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

/// <summary>Mode <c>fake</c> : les scénarios du dépôt en version 1 publiée, comme après le seed, perdus à l'arrêt.</summary>
public sealed class InMemoryScenarioCatalog : IScenarioCatalog
{
    private readonly ConcurrentDictionary<string, ScenarioEntry> _entries = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<(string Id, int Version), string> _sources = new();
    private readonly Lock _writes = new();

    public InMemoryScenarioCatalog(IScenarioDocuments documents)
    {
        foreach (var yaml in YamlScenarioDocuments.RepositoryScenarios())
        {
            var document = documents.Parse(yaml);
            _entries[document.Id] = new ScenarioEntry(document.Id, document.Title, document.Level, 1, 1, document.ContentSha256, null);
            _sources[(document.Id, 1)] = yaml;
        }
    }

    public Task<IReadOnlyList<ScenarioEntry>> ListAsync(CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<ScenarioEntry>>([.. _entries.Values.OrderBy(e => e.Id, StringComparer.Ordinal)]);

    public Task<ScenarioEntry?> FindAsync(string id, CancellationToken cancellationToken) => Task.FromResult(_entries.GetValueOrDefault(id));

    public Task<bool> TryAddVersionAsync(NewScenarioVersion version, CancellationToken cancellationToken)
    {
        var document = version.Document;
        lock (_writes)
        {
            if (!_sources.TryAdd((document.Id, version.Version), version.Source))
            {
                return Task.FromResult(false);
            }
            var published = _entries.GetValueOrDefault(document.Id)?.PublishedVersion;
            _entries[document.Id] = new ScenarioEntry(document.Id, document.Title, document.Level, published, version.Version, document.ContentSha256, null);
            return Task.FromResult(true);
        }
    }

    public Task<bool> SetPublishedVersionAsync(string id, int version, CancellationToken cancellationToken) =>
        Task.FromResult(Update(id, e => e with { PublishedVersion = version }));

    public Task<bool> SetArchivedAtAsync(string id, DateTimeOffset archivedAt, CancellationToken cancellationToken) =>
        Task.FromResult(Update(id, e => e with { ArchivedAt = archivedAt }));

    public Task<string?> SourceOfAsync(string id, int version, CancellationToken cancellationToken) =>
        Task.FromResult(_sources.GetValueOrDefault((id, version)));

    private bool Update(string id, Func<ScenarioEntry, ScenarioEntry> change)
    {
        lock (_writes)
        {
            if (!_entries.TryGetValue(id, out var entry))
            {
                return false;
            }
            _entries[id] = change(entry);
            return true;
        }
    }
}
