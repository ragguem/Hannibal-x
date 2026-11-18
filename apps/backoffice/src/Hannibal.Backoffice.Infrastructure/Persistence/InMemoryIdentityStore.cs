using System.Collections.Concurrent;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

/// <summary>
/// Mode <c>fake</c> : rôles de <see cref="IdentityCatalog"/> et administrateur initial, comme après le seed,
/// sans base. Les sessions sont perdues à l'arrêt.
/// </summary>
public sealed class InMemoryIdentityStore : IIdentityStore
{
    private readonly ConcurrentDictionary<string, UserCredentials> _usersByName = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, SessionEntry> _sessionsByTokenHash = new(StringComparer.Ordinal);

    public InMemoryIdentityStore(IPasswordHasher hasher, InitialAdminOptions initialAdmin)
    {
        if (initialAdmin.Password is not null)
        {
            AddUser(initialAdmin.Username, hasher.Hash(initialAdmin.Password), RoleCode.Admin);
        }
    }

    public UserCredentials AddUser(string username, string passwordHash, string roleCode)
    {
        var user = new UserCredentials(Guid.CreateVersion7(), username, passwordHash, roleCode);
        _usersByName[username] = user;
        return user;
    }

    public void DisableUser(string username) => _usersByName.TryRemove(username, out _);

    public Task<UserCredentials?> FindActiveUserAsync(string username, CancellationToken cancellationToken) =>
        Task.FromResult(_usersByName.GetValueOrDefault(username));

    public Task<IReadOnlySet<string>> PermissionsOfAsync(string roleCode, CancellationToken cancellationToken)
    {
        var role = IdentityCatalog.Roles.SingleOrDefault(r => r.Code == roleCode);
        IReadOnlySet<string> permissions = (role?.Permissions ?? []).ToHashSet(StringComparer.Ordinal);
        return Task.FromResult(permissions);
    }

    public Task CreateSessionAsync(NewSession session, CancellationToken cancellationToken)
    {
        _sessionsByTokenHash[Key(session.TokenHash)] = new SessionEntry(session.Id, session.UserId, session.ExpiresAt, session.AbsoluteExpiresAt);
        return Task.CompletedTask;
    }

    public Task<ActiveSession?> FindSessionAsync(byte[] tokenHash, CancellationToken cancellationToken)
    {
        if (!_sessionsByTokenHash.TryGetValue(Key(tokenHash), out var entry) || entry.Revoked)
        {
            return Task.FromResult<ActiveSession?>(null);
        }
        var user = _usersByName.Values.SingleOrDefault(u => u.Id == entry.UserId);
        return Task.FromResult(user is null
            ? null
            : new ActiveSession(entry.Id, user.Id, user.Username, user.RoleCode, entry.ExpiresAt, entry.AbsoluteExpiresAt));
    }

    public Task ExtendSessionAsync(Guid sessionId, DateTimeOffset expiresAt, CancellationToken cancellationToken)
    {
        foreach (var (key, entry) in _sessionsByTokenHash.Where(pair => pair.Value.Id == sessionId))
        {
            _sessionsByTokenHash[key] = entry with { ExpiresAt = expiresAt };
        }
        return Task.CompletedTask;
    }

    public Task RevokeSessionAsync(byte[] tokenHash, DateTimeOffset revokedAt, CancellationToken cancellationToken)
    {
        if (_sessionsByTokenHash.TryGetValue(Key(tokenHash), out var entry))
        {
            _sessionsByTokenHash[Key(tokenHash)] = entry with { Revoked = true };
        }
        return Task.CompletedTask;
    }

    private static string Key(byte[] tokenHash) => Convert.ToHexString(tokenHash);

    private sealed record SessionEntry(Guid Id, Guid UserId, DateTimeOffset ExpiresAt, DateTimeOffset AbsoluteExpiresAt, bool Revoked = false);
}
