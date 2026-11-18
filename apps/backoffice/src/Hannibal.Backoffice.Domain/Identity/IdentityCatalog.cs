namespace Hannibal.Backoffice.Domain.Identity;

/// <summary>Permissions vérifiées à la route (ADR 0007). Le nom est le contrat : ne pas renommer, en ajouter.</summary>
public static class Permission
{
    public const string MissionPlay = "mission:play";
    public const string CommandSubmit = "command:submit";
    public const string CommandDecide = "command:decide";
    public const string AuditRead = "audit:read";
    public const string UserManage = "user:manage";
}

public static class RoleCode
{
    public const string Operator = "operator";
    public const string Supervisor = "supervisor";
    public const string Admin = "admin";
}

public sealed record RoleDefinition(string Code, string Label, IReadOnlyList<string> Permissions);

public sealed record GameRoleDefinition(string Code, string Label, string Description);

/// <summary>Données de référence de l'identité, semées au démarrage. Retirer une ligne ici ne la supprime pas en base.</summary>
public static class IdentityCatalog
{
    public static readonly IReadOnlyList<RoleDefinition> Roles =
    [
        new(RoleCode.Operator, "Opérateur", [Permission.MissionPlay, Permission.CommandSubmit]),
        new(
            RoleCode.Supervisor,
            "Superviseur",
            [Permission.MissionPlay, Permission.CommandSubmit, Permission.CommandDecide, Permission.AuditRead]),
        new(
            RoleCode.Admin,
            "Administrateur",
            [Permission.MissionPlay, Permission.CommandSubmit, Permission.CommandDecide, Permission.AuditRead, Permission.UserManage]),
    ];

    public static readonly IReadOnlyList<GameRoleDefinition> GameRoles =
    [
        new("guide", "Guide", "Commande la formation et ordonne aux autres navires"),
        new("escort", "Escorte", "Tient son navire et exécute les ordres du guide"),
    ];
}
