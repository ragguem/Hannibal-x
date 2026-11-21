using System.Text.RegularExpressions;

namespace Hannibal.Backoffice.Application.Catalog;

/// <summary>
/// Catalogue des navires (Lot 7.3). Rien n'est supprimé : un navire retiré n'est plus proposé à la planification,
/// une classe reste tant qu'un navire la référence. Les bornes de vitesse alimentent la photo de mission (Lot 7.5).
/// </summary>
public sealed partial class Ships(IShipCatalog catalog, TimeProvider clock)
{
    public const int MaxSpeedKnots = 60;
    public const double MaxTurnRadiusMeters = 5000;
    public const double MaxLengthMeters = 500;
    private const int MaxLabelLength = 64;

    [GeneratedRegex("^[a-z][a-z0-9_-]{1,31}$")]
    private static partial Regex AcceptedClassCode();

    [GeneratedRegex("^[a-z][a-z0-9-]{1,23}$")]
    private static partial Regex AcceptedCallSign();

    public Task<IReadOnlyList<ShipClass>> ListClassesAsync(CancellationToken cancellationToken) => catalog.ListClassesAsync(cancellationToken);

    public async Task<ShipClass> CreateClassAsync(ShipClass shipClass, CancellationToken cancellationToken)
    {
        shipClass = shipClass with { Label = shipClass.Label.Trim() };
        if (!AcceptedClassCode().IsMatch(shipClass.Code))
        {
            throw new RuleViolation(RuleKind.Invalid, "code de classe refusé");
        }
        RequireValid(shipClass);
        if (!await catalog.TryCreateClassAsync(shipClass, cancellationToken).ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.Conflict, "code de classe déjà pris");
        }
        return shipClass;
    }

    public async Task<ShipClass> UpdateClassAsync(ShipClass shipClass, CancellationToken cancellationToken)
    {
        shipClass = shipClass with { Label = shipClass.Label.Trim() };
        RequireValid(shipClass);
        if (!await catalog.UpdateClassAsync(shipClass, cancellationToken).ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.NotFound, "classe inconnue");
        }
        return shipClass;
    }

    public Task<IReadOnlyList<Ship>> ListShipsAsync(CancellationToken cancellationToken) => catalog.ListShipsAsync(cancellationToken);

    public async Task<Ship> CreateShipAsync(string callSign, string classCode, CancellationToken cancellationToken)
    {
        if (!AcceptedCallSign().IsMatch(callSign))
        {
            throw new RuleViolation(RuleKind.Invalid, "nom d'appel refusé");
        }
        await RequireKnownClassAsync(classCode, cancellationToken).ConfigureAwait(false);
        var ship = new Ship(Guid.CreateVersion7(), callSign, classCode, clock.GetUtcNow(), null);
        if (!await catalog.TryCreateShipAsync(ship, cancellationToken).ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.Conflict, "nom d'appel déjà pris");
        }
        return await RequireShipAsync(ship.Id, cancellationToken).ConfigureAwait(false);
    }

    public async Task<Ship> ChangeClassAsync(Guid shipId, string classCode, CancellationToken cancellationToken)
    {
        await RequireKnownClassAsync(classCode, cancellationToken).ConfigureAwait(false);
        await RequireFoundAsync(catalog.SetShipClassAsync(shipId, classCode, cancellationToken)).ConfigureAwait(false);
        return await RequireShipAsync(shipId, cancellationToken).ConfigureAwait(false);
    }

    public async Task<Ship> RetireAsync(Guid shipId, CancellationToken cancellationToken)
    {
        await RequireFoundAsync(catalog.SetRetiredAtAsync(shipId, clock.GetUtcNow(), cancellationToken)).ConfigureAwait(false);
        return await RequireShipAsync(shipId, cancellationToken).ConfigureAwait(false);
    }

    public async Task<Ship> ReactivateAsync(Guid shipId, CancellationToken cancellationToken)
    {
        await RequireFoundAsync(catalog.SetRetiredAtAsync(shipId, null, cancellationToken)).ConfigureAwait(false);
        return await RequireShipAsync(shipId, cancellationToken).ConfigureAwait(false);
    }

    private static void RequireValid(ShipClass c)
    {
        if (c.Label.Length == 0 || c.Label.Length > MaxLabelLength)
        {
            throw new RuleViolation(RuleKind.Invalid, "libellé de classe refusé");
        }
        if (c.MinSpeedKnots <= 0 || c.MinSpeedKnots > c.MaxSpeedKnots || c.MaxSpeedKnots > MaxSpeedKnots)
        {
            throw new RuleViolation(RuleKind.Invalid, "bornes de vitesse refusées");
        }
        if (!(c.TurnRadiusMeters > 0 && c.TurnRadiusMeters <= MaxTurnRadiusMeters) || !(c.LengthMeters > 0 && c.LengthMeters <= MaxLengthMeters))
        {
            throw new RuleViolation(RuleKind.Invalid, "rayon de giration ou longueur refusés");
        }
    }

    private async Task RequireKnownClassAsync(string classCode, CancellationToken cancellationToken)
    {
        if (await catalog.FindClassAsync(classCode, cancellationToken).ConfigureAwait(false) is null)
        {
            throw new RuleViolation(RuleKind.Invalid, "classe inconnue");
        }
    }

    private async Task<Ship> RequireShipAsync(Guid shipId, CancellationToken cancellationToken) =>
        await catalog.FindShipAsync(shipId, cancellationToken).ConfigureAwait(false)
        ?? throw new RuleViolation(RuleKind.NotFound, "navire inconnu");

    private static async Task RequireFoundAsync(Task<bool> update)
    {
        if (!await update.ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.NotFound, "navire inconnu");
        }
    }
}
