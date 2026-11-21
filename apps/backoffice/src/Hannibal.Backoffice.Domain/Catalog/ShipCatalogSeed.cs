namespace Hannibal.Backoffice.Domain.Catalog;

public sealed record ShipClassDefinition(
    string Code,
    string Label,
    int MinSpeedKnots,
    int MaxSpeedKnots,
    double TurnRadiusMeters,
    double LengthMeters);

public sealed record ShipDefinition(string CallSign, string ClassCode);

/// <summary>
/// Classes et navires inventés, semés une seule fois : ce que l'administrateur modifie ensuite n'est plus écrasé.
/// Les noms d'appel sont ceux des scénarios du dépôt.
/// </summary>
public static class ShipCatalogSeed
{
    public static readonly IReadOnlyList<ShipClassDefinition> Classes =
    [
        new("fregate", "Frégate", 3, 28, 600, 142),
        new("aviso", "Aviso", 3, 24, 400, 81),
    ];

    public static readonly IReadOnlyList<ShipDefinition> Ships =
    [
        new("hannibal", "fregate"),
        new("alfa", "fregate"),
        new("charlie", "aviso"),
        new("delta", "aviso"),
    ];
}
