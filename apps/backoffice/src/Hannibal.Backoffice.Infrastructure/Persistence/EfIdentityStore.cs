using Hannibal.Backoffice.Application.Identity;
using Microsoft.EntityFrameworkCore;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

public sealed class EfIdentityStore(BackofficeDbContext dbContext) : IIdentityStore
{
    public async Task<UserCredentials?> FindActiveUserAsync(string username, CancellationToken cancellationToken) =>
        await dbContext.Users.AsNoTracking()
            .Where(u => u.Username == username && u.DisabledAt == null)
            .Select(u => new UserCredentials(u.Id, u.Username, u.PasswordHash, u.RoleCode))
            .SingleOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

    public async Task<IReadOnlySet<string>> PermissionsOfAsync(string roleCode, CancellationToken cancellationToken)
    {
        var permissions = await dbContext.RolePermissions.AsNoTracking()
            .Where(p => p.RoleCode == roleCode)
            .Select(p => p.Permission)
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
        return permissions.ToHashSet(StringComparer.Ordinal);
    }

    public async Task CreateSessionAsync(NewSession session, CancellationToken cancellationToken)
    {
        dbContext.Sessions.Add(new SessionRow
        {
            Id = session.Id,
            UserId = session.UserId,
            TokenHash = session.TokenHash,
            ExpiresAt = session.ExpiresAt,
            AbsoluteExpiresAt = session.AbsoluteExpiresAt,
        });
        await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
    }

    public async Task<ActiveSession?> FindSessionAsync(byte[] tokenHash, CancellationToken cancellationToken) =>
        await dbContext.Sessions.AsNoTracking()
            .Where(s => s.TokenHash == tokenHash && s.RevokedAt == null)
            .Join(
                dbContext.Users.Where(u => u.DisabledAt == null),
                s => s.UserId,
                u => u.Id,
                (s, u) => new ActiveSession(s.Id, u.Id, u.Username, u.RoleCode, s.ExpiresAt, s.AbsoluteExpiresAt))
            .SingleOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

    public Task ExtendSessionAsync(Guid sessionId, DateTimeOffset expiresAt, CancellationToken cancellationToken) =>
        dbContext.Sessions.Where(s => s.Id == sessionId)
            .ExecuteUpdateAsync(s => s.SetProperty(row => row.ExpiresAt, expiresAt), cancellationToken);

    public Task RevokeSessionAsync(byte[] tokenHash, DateTimeOffset revokedAt, CancellationToken cancellationToken) =>
        dbContext.Sessions.Where(s => s.TokenHash == tokenHash && s.RevokedAt == null)
            .ExecuteUpdateAsync(s => s.SetProperty(row => row.RevokedAt, revokedAt), cancellationToken);
}
