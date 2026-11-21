using System.Collections.Concurrent;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

/// <summary>
/// Mode <c>fake</c> : rôles de <see cref="IdentityCatalog"/> et administrateur initial, comme après le seed,
/// sans base. Comptes et sessions sont perdus à l'arrêt.
/// </summary>
public sealed class InMemoryIdentityStore : IIdentityStore, IUserDirectory
{
    private readonly ConcurrentDictionary<Guid, UserEntry> _usersById = new();
    private readonly ConcurrentDictionary<string, SessionEntry> _sessionsByTokenHash = new(StringComparer.Ordinal);
    private readonly Lock _creation = new();

    public InMemoryIdentityStore(IPasswordHasher hasher, InitialAdminOptions initialAdmin)
    {
        if (initialAdmin.Password is not null)
        {
            AddUser(initialAdmin.Username, hasher.Hash(initialAdmin.Password), RoleCode.Admin);
        }
    }

    public UserCredentials AddUser(string username, string passwordHash, string roleCode)
    {
        var entry = new UserEntry(Guid.CreateVersion7(), username, passwordHash, roleCode, DateTimeOffset.UtcNow, null, null);
        _usersById[entry.Id] = entry;
        return new UserCredentials(entry.Id, username, passwordHash, roleCode);
    }

    public void DisableUser(string username)
    {
        foreach (var entry in _usersById.Values.Where(u => u.Username == username))
        {
            _usersById[entry.Id] = entry with { DisabledAt = DateTimeOffset.UtcNow };
        }
    }

    public Task<UserCredentials?> FindActiveUserAsync(string username, CancellationToken cancellationToken) =>
        Task.FromResult(_usersById.Values
            .Where(u => u.Username == username && u.DisabledAt is null)
            .Select(u => new UserCredentials(u.Id, u.Username, u.PasswordHash, u.RoleCode))
            .SingleOrDefault());

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
        if (!_sessionsByTokenHash.TryGetValue(Key(tokenHash), out var entry) || entry.Revoked
            || !_usersById.TryGetValue(entry.UserId, out var user) || user.DisabledAt is not null)
        {
            return Task.FromResult<ActiveSession?>(null);
        }
        return Task.FromResult<ActiveSession?>(
            new ActiveSession(entry.Id, user.Id, user.Username, user.RoleCode, entry.ExpiresAt, entry.AbsoluteExpiresAt));
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

    public Task<IReadOnlyList<UserSummary>> ListAsync(CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<UserSummary>>([.. _usersById.Values.OrderBy(u => u.Username, StringComparer.Ordinal).Select(Summary)]);

    public Task<UserSummary?> FindAsync(Guid id, CancellationToken cancellationToken) =>
        Task.FromResult(_usersById.TryGetValue(id, out var user) ? Summary(user) : null);

    public Task<bool> TryCreateAsync(NewUser user, CancellationToken cancellationToken)
    {
        lock (_creation)
        {
            if (_usersById.Values.Any(u => u.Username == user.Username))
            {
                return Task.FromResult(false);
            }
            _usersById[user.Id] = new UserEntry(user.Id, user.Username, user.PasswordHash, user.RoleCode, user.CreatedAt, null, null);
            return Task.FromResult(true);
        }
    }

    public Task<bool> SetRoleAsync(Guid id, string roleCode, CancellationToken cancellationToken) =>
        Update(id, u => u with { RoleCode = roleCode });

    public Task<bool> SetDisabledAtAsync(Guid id, DateTimeOffset? disabledAt, CancellationToken cancellationToken) =>
        Update(id, u => u with { DisabledAt = disabledAt });

    public Task<bool> SetPasswordAsync(Guid id, string passwordHash, DateTimeOffset? changedAt, CancellationToken cancellationToken) =>
        Update(id, u => u with { PasswordHash = passwordHash, PasswordChangedAt = changedAt });

    public Task<string?> PasswordHashOfAsync(Guid id, CancellationToken cancellationToken) =>
        Task.FromResult(_usersById.TryGetValue(id, out var user) && user.DisabledAt is null ? user.PasswordHash : null);

    public Task RevokeSessionsAsync(Guid userId, DateTimeOffset revokedAt, CancellationToken cancellationToken)
    {
        foreach (var (key, entry) in _sessionsByTokenHash.Where(pair => pair.Value.UserId == userId))
        {
            _sessionsByTokenHash[key] = entry with { Revoked = true };
        }
        return Task.CompletedTask;
    }

    private Task<bool> Update(Guid id, Func<UserEntry, UserEntry> change)
    {
        if (!_usersById.TryGetValue(id, out var user))
        {
            return Task.FromResult(false);
        }
        _usersById[id] = change(user);
        return Task.FromResult(true);
    }

    private static UserSummary Summary(UserEntry u) => new(u.Id, u.Username, u.RoleCode, u.CreatedAt, u.DisabledAt, u.PasswordChangedAt);

    private static string Key(byte[] tokenHash) => Convert.ToHexString(tokenHash);

    private sealed record UserEntry(
        Guid Id,
        string Username,
        string PasswordHash,
        string RoleCode,
        DateTimeOffset CreatedAt,
        DateTimeOffset? DisabledAt,
        DateTimeOffset? PasswordChangedAt);

    private sealed record SessionEntry(Guid Id, Guid UserId, DateTimeOffset ExpiresAt, DateTimeOffset AbsoluteExpiresAt, bool Revoked = false);
}
