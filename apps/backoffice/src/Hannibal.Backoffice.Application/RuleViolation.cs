namespace Hannibal.Backoffice.Application;

public enum RuleKind
{
    NotFound,
    Conflict,
    Invalid,
}

/// <summary>Règle de gestion refusée ; traduite en 404, 409 ou 422 avec un code stable.</summary>
public sealed class RuleViolation(RuleKind kind, string detail) : Exception(detail)
{
    public RuleKind Kind { get; } = kind;
}
