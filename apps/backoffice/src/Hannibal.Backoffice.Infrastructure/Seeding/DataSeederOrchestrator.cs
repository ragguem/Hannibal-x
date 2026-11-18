using System.Diagnostics;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Seeding.Abstraction;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace Hannibal.Backoffice.Infrastructure.Seeding;

/// <summary>
/// Exécute les <see cref="IDataSeeder"/> par <see cref="IDataSeeder.Order"/> croissant, chacun dans sa transaction.
/// Un échec annule ce seeder seulement : la chaîne continue, puis les échecs sont levés ensemble à la fin,
/// pour que la panne d'une famille de données n'en prive pas les suivantes.
/// </summary>
public sealed class DataSeederOrchestrator(
    IEnumerable<IDataSeeder> seeders,
    BackofficeDbContext dbContext,
    ILogger<DataSeederOrchestrator> logger)
{
    public async Task SeedAllAsync(CancellationToken cancellationToken)
    {
        var ordered = seeders.OrderBy(s => s.Order).ToList();
        var failures = new List<Exception>();
        var total = Stopwatch.StartNew();

        foreach (var seeder in ordered)
        {
            var elapsed = Stopwatch.StartNew();
            try
            {
                await RunInTransactionAsync(seeder, cancellationToken).ConfigureAwait(false);
                logger.LogInformation("Seeder {SeederName} (ordre {SeederOrder}) terminé en {ElapsedMs} ms", seeder.Name, seeder.Order, elapsed.ElapsedMilliseconds);
            }
            catch (Exception error) when (error is not OperationCanceledException)
            {
                // Le contexte est partagé par toute la chaîne : sans purge, les entités du seeder annulé
                // seraient écrites par le SaveChanges du suivant.
                dbContext.ChangeTracker.Clear();
                logger.LogError(error, "Seeder {SeederName} (ordre {SeederOrder}) en échec, transaction annulée, chaîne poursuivie", seeder.Name, seeder.Order);
                failures.Add(new InvalidOperationException($"Seeder « {seeder.Name} » (ordre {seeder.Order}) en échec : {error.Message}", error));
            }
        }

        if (failures.Count > 0)
        {
            logger.LogCritical("{FailedCount} seeder(s) en échec sur {SeederCount} en {ElapsedMs} ms", failures.Count, ordered.Count, total.ElapsedMilliseconds);
            throw new AggregateException($"{failures.Count} seeder(s) en échec sur {ordered.Count}. Les autres données ont été semées.", failures);
        }
        logger.LogInformation("{SeederCount} seeder(s) terminés en {ElapsedMs} ms", ordered.Count, total.ElapsedMilliseconds);
    }

    private async Task RunInTransactionAsync(IDataSeeder seeder, CancellationToken cancellationToken)
    {
        await using var transaction = await dbContext.Database.BeginTransactionAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            await seeder.SeedAsync(cancellationToken).ConfigureAwait(false);
            await transaction.CommitAsync(cancellationToken).ConfigureAwait(false);
        }
        catch
        {
            try
            {
                await transaction.RollbackAsync(CancellationToken.None).ConfigureAwait(false);
            }
            catch (Exception rollbackError)
            {
                // L'exception d'origine reste celle qui est levée : c'est la seule utile au diagnostic.
                logger.LogError(rollbackError, "Annulation de la transaction du seeder {SeederName} en échec", seeder.Name);
            }
            throw;
        }
    }
}
