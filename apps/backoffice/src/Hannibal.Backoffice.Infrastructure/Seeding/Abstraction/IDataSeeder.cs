namespace Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;

/// <summary>
/// Seeder d'une famille de données de référence. Exécuté par <see cref="DataSeederOrchestrator"/>
/// dans l'ordre croissant de <see cref="Order"/>, chacun dans sa transaction.
/// </summary>
public interface IDataSeeder
{
    /// <summary>Ordre relatif ; laisser des trous (10, 20, 30…) pour insérer un seeder sans renuméroter.</summary>
    int Order { get; }

    /// <summary>Nom lisible pour les journaux.</summary>
    string Name { get; }

    /// <summary>UPSERT idempotent par clé métier : ajoute ce qui manque, aligne ce qui diffère, ne supprime jamais.</summary>
    Task SeedAsync(CancellationToken cancellationToken);
}
