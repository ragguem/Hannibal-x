using Hannibal.Backoffice.Application.Identity;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

/// <summary>Chaque écriture retire aussi les sessions du compte du cache de cette instance.</summary>
public sealed class EfUserDirectory(BackofficeDbContext dbContext, IdentityCache cache) : IUserDirectory
{
    public async Task<IReadOnlyList<UserSummary>> ListAsync(CancellationToken cancellationToken) =>
        await dbContext.Users.AsNoTracking()
            .OrderBy(u => u.Username)
            .Select(u => new UserSummary(u.Id, u.Username, u.RoleCode, u.CreatedAt, u.DisabledAt, u.PasswordChangedAt))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

    public async Task<UserSummary?> FindAsync(Guid id, CancellationToken cancellationToken) =>
        await dbContext.Users.AsNoTracking()
            .Where(u => u.Id == id)
            .Select(u => new UserSummary(u.Id, u.Username, u.RoleCode, u.CreatedAt, u.DisabledAt, u.PasswordChangedAt))
            .SingleOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

    public async Task<bool> TryCreateAsync(NewUser user, CancellationToken cancellationToken)
    {
        dbContext.Users.Add(new UserAccountRow
        {
            Id = user.Id,
            Username = user.Username,
            PasswordHash = user.PasswordHash,
            RoleCode = user.RoleCode,
            CreatedAt = user.CreatedAt,
        });
        try
        {
            await dbContext.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
            return true;
        }
        catch (DbUpdateException e) when (e.InnerException is PostgresException { SqlState: PostgresErrorCodes.UniqueViolation })
        {
            dbContext.ChangeTracker.Clear();
            return false;
        }
    }

    public Task<bool> SetRoleAsync(Guid id, string roleCode, CancellationToken cancellationToken) =>
        UpdateAsync(id, u => u.SetProperty(row => row.RoleCode, roleCode), cancellationToken);

    public Task<bool> SetDisabledAtAsync(Guid id, DateTimeOffset? disabledAt, CancellationToken cancellationToken) =>
        UpdateAsync(id, u => u.SetProperty(row => row.DisabledAt, disabledAt), cancellationToken);

    public Task<bool> SetPasswordAsync(Guid id, string passwordHash, DateTimeOffset? changedAt, CancellationToken cancellationToken) =>
        UpdateAsync(id, u => u.SetProperty(row => row.PasswordHash, passwordHash).SetProperty(row => row.PasswordChangedAt, changedAt), cancellationToken);

    public async Task<string?> PasswordHashOfAsync(Guid id, CancellationToken cancellationToken) =>
        await dbContext.Users.AsNoTracking()
            .Where(u => u.Id == id && u.DisabledAt == null)
            .Select(u => u.PasswordHash)
            .SingleOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

    public async Task RevokeSessionsAsync(Guid userId, DateTimeOffset revokedAt, CancellationToken cancellationToken)
    {
        await dbContext.Sessions.Where(s => s.UserId == userId && s.RevokedAt == null)
            .ExecuteUpdateAsync(s => s.SetProperty(row => row.RevokedAt, revokedAt), cancellationToken)
            .ConfigureAwait(false);
        cache.ForgetUser(userId);
    }

    private async Task<bool> UpdateAsync(
        Guid id,
        Action<Microsoft.EntityFrameworkCore.Query.UpdateSettersBuilder<UserAccountRow>> setters,
        CancellationToken cancellationToken)
    {
        var updated = await dbContext.Users.Where(u => u.Id == id).ExecuteUpdateAsync(setters, cancellationToken).ConfigureAwait(false);
        cache.ForgetUser(id);
        return updated > 0;
    }
}
