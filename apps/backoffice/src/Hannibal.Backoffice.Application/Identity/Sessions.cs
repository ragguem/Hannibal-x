using System.Security.Cryptography;
using System.Text;
using Hannibal.Backoffice.Domain.Identity;

namespace Hannibal.Backoffice.Application.Identity;

public sealed record SignedIn(string Token, AuthenticatedUser User, DateTimeOffset ExpiresAt);

public sealed record CurrentSession(AuthenticatedUser User, DateTimeOffset ExpiresAt);

/// <summary>Handlers <c>SignIn</c>, <c>Authenticate</c> et <c>SignOut</c> des comptes locaux.</summary>
public sealed class Sessions(IIdentityStore store, IPasswordHasher hasher, TimeProvider clock)
{
    private const int TokenBytes = 32;
    private readonly Lazy<string> _decoyHash = new(() => hasher.Hash(Convert.ToBase64String(RandomNumberGenerator.GetBytes(16))));

    /// <summary>Compte inconnu, désactivé ou mauvais mot de passe : même réponse et même coût de calcul.</summary>
    public async Task<SignedIn?> SignInAsync(string username, string password, CancellationToken cancellationToken)
    {
        var user = await store.FindActiveUserAsync(username, cancellationToken).ConfigureAwait(false);
        var verified = hasher.Verify(password, user?.PasswordHash ?? _decoyHash.Value);
        if (user is null || !verified)
        {
            return null;
        }
        var token = Base64Url(RandomNumberGenerator.GetBytes(TokenBytes));
        var now = clock.GetUtcNow();
        var absoluteExpiresAt = now + SessionPolicy.AbsoluteTimeout;
        var expiresAt = SessionPolicy.NextExpiry(now, absoluteExpiresAt);
        await store.CreateSessionAsync(new NewSession(Guid.CreateVersion7(), user.Id, HashToken(token), expiresAt, absoluteExpiresAt), cancellationToken).ConfigureAwait(false);
        var permissions = await store.PermissionsOfAsync(user.RoleCode, cancellationToken).ConfigureAwait(false);
        return new SignedIn(token, new AuthenticatedUser(user.Id, user.Username, user.RoleCode, permissions), expiresAt);
    }

    /// <summary>Session valide : prolongée (dans la limite absolue) et renvoyée ; <c>null</c> sinon.</summary>
    public async Task<CurrentSession?> AuthenticateAsync(string token, CancellationToken cancellationToken)
    {
        var session = await store.FindSessionAsync(HashToken(token), cancellationToken).ConfigureAwait(false);
        var now = clock.GetUtcNow();
        if (session is null || session.ExpiresAt <= now || session.AbsoluteExpiresAt <= now)
        {
            return null;
        }
        var expiresAt = SessionPolicy.NextExpiry(now, session.AbsoluteExpiresAt);
        await store.ExtendSessionAsync(session.Id, expiresAt, cancellationToken).ConfigureAwait(false);
        var permissions = await store.PermissionsOfAsync(session.RoleCode, cancellationToken).ConfigureAwait(false);
        return new CurrentSession(new AuthenticatedUser(session.UserId, session.Username, session.RoleCode, permissions), expiresAt);
    }

    public Task SignOutAsync(string token, CancellationToken cancellationToken) =>
        store.RevokeSessionAsync(HashToken(token), clock.GetUtcNow(), cancellationToken);

    private static byte[] HashToken(string token) => SHA256.HashData(Encoding.UTF8.GetBytes(token));

    private static string Base64Url(byte[] bytes) => Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');
}
