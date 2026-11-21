using System.Collections.Concurrent;
using Hannibal.Backoffice.Application.Identity;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

/// <summary>
/// Sessions et permissions gardées en mémoire de l'instance, pour qu'une requête relayée ne touche plus la base.
/// Une révocation faite sur une autre instance, ou un compte désactivé, n'est vue qu'après <see cref="SessionLifetime"/>.
/// </summary>
public sealed class IdentityCache(TimeProvider clock)
{
    public static readonly TimeSpan SessionLifetime = TimeSpan.FromSeconds(30);
    public static readonly TimeSpan PermissionsLifetime = TimeSpan.FromMinutes(5);
    private const int PruneThreshold = 10_000;

    private readonly ConcurrentDictionary<string, Cached<ActiveSession>> _sessionsByTokenHash = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<Guid, string> _tokenHashBySessionId = new();
    private readonly ConcurrentDictionary<string, Cached<IReadOnlySet<string>>> _permissionsByRole = new(StringComparer.Ordinal);

    public ActiveSession? FindSession(byte[] tokenHash) => Fresh(_sessionsByTokenHash, Key(tokenHash));

    public void KeepSession(byte[] tokenHash, ActiveSession session)
    {
        if (_sessionsByTokenHash.Count >= PruneThreshold)
        {
            PruneExpiredSessions();
        }
        var key = Key(tokenHash);
        _sessionsByTokenHash[key] = new Cached<ActiveSession>(session, clock.GetUtcNow() + SessionLifetime);
        _tokenHashBySessionId[session.Id] = key;
    }

    public void ExtendSession(Guid sessionId, DateTimeOffset expiresAt)
    {
        if (_tokenHashBySessionId.TryGetValue(sessionId, out var key) && _sessionsByTokenHash.TryGetValue(key, out var cached))
        {
            _sessionsByTokenHash.TryUpdate(key, cached with { Value = cached.Value with { ExpiresAt = expiresAt } }, cached);
        }
    }

    public void ForgetSession(byte[] tokenHash)
    {
        if (_sessionsByTokenHash.TryRemove(Key(tokenHash), out var cached))
        {
            _tokenHashBySessionId.TryRemove(cached.Value.Id, out _);
        }
    }

    public IReadOnlySet<string>? FindPermissions(string roleCode) => Fresh(_permissionsByRole, roleCode);

    public void KeepPermissions(string roleCode, IReadOnlySet<string> permissions) =>
        _permissionsByRole[roleCode] = new Cached<IReadOnlySet<string>>(permissions, clock.GetUtcNow() + PermissionsLifetime);

    private T? Fresh<T>(ConcurrentDictionary<string, Cached<T>> entries, string key)
        where T : class =>
        entries.TryGetValue(key, out var cached) && cached.Until > clock.GetUtcNow() ? cached.Value : null;

    private void PruneExpiredSessions()
    {
        var now = clock.GetUtcNow();
        foreach (var (key, cached) in _sessionsByTokenHash.Where(pair => pair.Value.Until <= now))
        {
            if (_sessionsByTokenHash.TryRemove(key, out _))
            {
                _tokenHashBySessionId.TryRemove(cached.Value.Id, out _);
            }
        }
    }

    private static string Key(byte[] tokenHash) => Convert.ToHexString(tokenHash);

    private sealed record Cached<T>(T Value, DateTimeOffset Until);
}

/// <summary>Magasin d'identité qui lit d'abord <see cref="IdentityCache"/> et le tient à jour à chaque écriture.</summary>
public sealed class CachedIdentityStore(IIdentityStore inner, IdentityCache cache) : IIdentityStore
{
    public Task<UserCredentials?> FindActiveUserAsync(string username, CancellationToken cancellationToken) =>
        inner.FindActiveUserAsync(username, cancellationToken);

    public async Task<IReadOnlySet<string>> PermissionsOfAsync(string roleCode, CancellationToken cancellationToken)
    {
        if (cache.FindPermissions(roleCode) is { } cached)
        {
            return cached;
        }
        var permissions = await inner.PermissionsOfAsync(roleCode, cancellationToken).ConfigureAwait(false);
        cache.KeepPermissions(roleCode, permissions);
        return permissions;
    }

    public Task CreateSessionAsync(NewSession session, CancellationToken cancellationToken) =>
        inner.CreateSessionAsync(session, cancellationToken);

    public async Task<ActiveSession?> FindSessionAsync(byte[] tokenHash, CancellationToken cancellationToken)
    {
        if (cache.FindSession(tokenHash) is { } cached)
        {
            return cached;
        }
        var session = await inner.FindSessionAsync(tokenHash, cancellationToken).ConfigureAwait(false);
        if (session is not null)
        {
            cache.KeepSession(tokenHash, session);
        }
        return session;
    }

    public async Task ExtendSessionAsync(Guid sessionId, DateTimeOffset expiresAt, CancellationToken cancellationToken)
    {
        await inner.ExtendSessionAsync(sessionId, expiresAt, cancellationToken).ConfigureAwait(false);
        cache.ExtendSession(sessionId, expiresAt);
    }

    public async Task RevokeSessionAsync(byte[] tokenHash, DateTimeOffset revokedAt, CancellationToken cancellationToken)
    {
        await inner.RevokeSessionAsync(tokenHash, revokedAt, cancellationToken).ConfigureAwait(false);
        cache.ForgetSession(tokenHash);
    }
}
