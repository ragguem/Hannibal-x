namespace Hannibal.Backoffice.Application.Catalog;

/// <summary>Document YAML validé : <see cref="Json"/> est ce que la photo de mission transportera.</summary>
public sealed record ParsedScenario(string Id, string Title, string Level, IReadOnlyList<string> Fleet, string Json, string ContentSha256);

public sealed record ScenarioEntry(
    string Id,
    string Title,
    string Level,
    int? PublishedVersion,
    int LatestVersion,
    string LatestSha256,
    DateTimeOffset? ArchivedAt);

public sealed record NewScenarioVersion(ParsedScenario Document, int Version, string Source, Guid? ImportedBy, DateTimeOffset ImportedAt);

/// <summary>Lit un scénario YAML et le valide contre le JSON Schema de <c>packages/contracts</c>.</summary>
public interface IScenarioDocuments
{
    /// <exception cref="RuleViolation">Document illisible ou non conforme, avec un message pour l'auteur.</exception>
    ParsedScenario Parse(string yaml);
}

public interface IScenarioCatalog
{
    Task<IReadOnlyList<ScenarioEntry>> ListAsync(CancellationToken cancellationToken);

    Task<ScenarioEntry?> FindAsync(string id, CancellationToken cancellationToken);

    /// <summary>Crée le scénario au premier import, sinon met à jour titre et niveau. <c>false</c> si la version existe déjà.</summary>
    Task<bool> TryAddVersionAsync(NewScenarioVersion version, CancellationToken cancellationToken);

    Task<bool> SetPublishedVersionAsync(string id, int version, CancellationToken cancellationToken);

    Task<bool> SetArchivedAtAsync(string id, DateTimeOffset archivedAt, CancellationToken cancellationToken);

    Task<string?> SourceOfAsync(string id, int version, CancellationToken cancellationToken);

    /// <summary>Document JSON d'une version, tel que la photo de mission le transporte.</summary>
    Task<string?> DocumentOfAsync(string id, int version, CancellationToken cancellationToken);
}
