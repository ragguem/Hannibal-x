namespace Hannibal.Backoffice.Application.Identity;

/// <summary><c>PasswordChangedAt</c> nul : mot de passe provisoire, fixé par un administrateur.</summary>
public sealed record UserSummary(
    Guid Id,
    string Username,
    string RoleCode,
    DateTimeOffset CreatedAt,
    DateTimeOffset? DisabledAt,
    DateTimeOffset? PasswordChangedAt);

public sealed record NewUser(Guid Id, string Username, string PasswordHash, string RoleCode, DateTimeOffset CreatedAt);

/// <summary>Gestion des comptes. Les méthodes <c>Set…</c> renvoient <c>false</c> si le compte n'existe pas.</summary>
public interface IUserDirectory
{
    Task<IReadOnlyList<UserSummary>> ListAsync(CancellationToken cancellationToken);

    Task<UserSummary?> FindAsync(Guid id, CancellationToken cancellationToken);

    /// <summary><c>false</c> si le nom est déjà pris.</summary>
    Task<bool> TryCreateAsync(NewUser user, CancellationToken cancellationToken);

    Task<bool> SetRoleAsync(Guid id, string roleCode, CancellationToken cancellationToken);

    Task<bool> SetDisabledAtAsync(Guid id, DateTimeOffset? disabledAt, CancellationToken cancellationToken);

    Task<bool> SetPasswordAsync(Guid id, string passwordHash, DateTimeOffset? changedAt, CancellationToken cancellationToken);

    /// <summary>Hachage du mot de passe d'un compte actif ; <c>null</c> sinon.</summary>
    Task<string?> PasswordHashOfAsync(Guid id, CancellationToken cancellationToken);

    Task RevokeSessionsAsync(Guid userId, DateTimeOffset revokedAt, CancellationToken cancellationToken);
}
