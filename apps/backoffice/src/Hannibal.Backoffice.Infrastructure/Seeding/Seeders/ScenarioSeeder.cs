using Hannibal.Backoffice.Application.Catalog;
using Hannibal.Backoffice.Infrastructure.Catalog;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;

namespace Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

/// <summary>
/// Scénarios du dépôt, importés et publiés s'ils sont absents. Clé : <c>id</c>. Après <see cref="ShipSeeder"/> :
/// leurs flottes doivent être au catalogue. Un scénario déjà présent n'est jamais réimporté.
/// </summary>
public sealed class ScenarioSeeder(Scenarios scenarios, IScenarioCatalog catalog, IScenarioDocuments documents) : IDataSeeder
{
    public int Order => 60;

    public string Name => nameof(ScenarioSeeder);

    public async Task SeedAsync(CancellationToken cancellationToken)
    {
        foreach (var yaml in YamlScenarioDocuments.RepositoryScenarios())
        {
            var id = documents.Parse(yaml).Id;
            if (await catalog.FindAsync(id, cancellationToken).ConfigureAwait(false) is not null)
            {
                continue;
            }
            var entry = await scenarios.ImportAsync(yaml, importedBy: null, cancellationToken).ConfigureAwait(false);
            await scenarios.PublishAsync(id, entry.LatestVersion, cancellationToken).ConfigureAwait(false);
        }
    }
}
