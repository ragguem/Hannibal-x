namespace Hannibal.Backoffice.Application;

public enum RuleKind
{
    NotFound,
    Conflict,
    Invalid,
    Unavailable,
}

/// <summary>
/// Règle de gestion refusée ; traduite en 404, 409, 422 ou 503 avec un code stable. <paramref name="publicMessage"/>
/// remplace le message générique quand l'utilisateur doit savoir quoi corriger (scénario importé).
/// </summary>
public sealed class RuleViolation(RuleKind kind, string detail, string? publicMessage = null) : Exception(detail)
{
    public RuleKind Kind { get; } = kind;

    public string? PublicMessage { get; } = publicMessage;
}
