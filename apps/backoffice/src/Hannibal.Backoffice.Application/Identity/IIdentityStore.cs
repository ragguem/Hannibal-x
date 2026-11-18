namespace Hannibal.Backoffice.Application.Identity;

public sealed record UserCredentials(Guid Id, string Username, string PasswordHash, string RoleCode);

public sealed record NewSession(Guid Id, Guid UserId, byte[] TokenHash, DateTimeOffset ExpiresAt, DateTimeOffset AbsoluteExpiresAt);

/// <summary>Session non révoquée d'un compte actif ; l'expiration est contrôlée par l'appelant.</summary>
public sealed record ActiveSession(Guid Id, Guid UserId, string Username, string RoleCode, DateTimeOffset ExpiresAt, DateTimeOffset AbsoluteExpiresAt);

/// <summary>Comptes, permissions et sessions. Les jetons ne sont jamais stockés, seulement leur SHA-256.</summary>
public interface IIdentityStore
{
    /// <summary>Compte non désactivé ; <c>null</c> sinon.</summary>
    Task<UserCredentials?> FindActiveUserAsync(string username, CancellationToken cancellationToken);

    Task<IReadOnlySet<string>> PermissionsOfAsync(string roleCode, CancellationToken cancellationToken);

    Task CreateSessionAsync(NewSession session, CancellationToken cancellationToken);

    /// <summary>Session non révoquée d'un compte non désactivé ; <c>null</c> sinon.</summary>
    Task<ActiveSession?> FindSessionAsync(byte[] tokenHash, CancellationToken cancellationToken);

    Task ExtendSessionAsync(Guid sessionId, DateTimeOffset expiresAt, CancellationToken cancellationToken);

    Task RevokeSessionAsync(byte[] tokenHash, DateTimeOffset revokedAt, CancellationToken cancellationToken);
}
