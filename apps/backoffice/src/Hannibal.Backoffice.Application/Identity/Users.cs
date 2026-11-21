using System.Security.Cryptography;
using System.Text.RegularExpressions;
using Hannibal.Backoffice.Domain.Identity;

namespace Hannibal.Backoffice.Application.Identity;

public sealed record IssuedPassword(UserSummary User, string TemporaryPassword);

/// <summary>
/// Gestion des comptes (Lot 7.2). Un administrateur ne peut ni se désactiver ni changer son propre rôle :
/// il reste toujours au moins un compte capable de gérer les autres.
/// </summary>
public sealed partial class Users(IUserDirectory directory, IPasswordHasher hasher, TimeProvider clock)
{
    public const int MinimumPasswordLength = 12;
    private const int TemporaryPasswordBytes = 16;

    [GeneratedRegex("^[a-z0-9._-]{3,32}$")]
    private static partial Regex AcceptedUsername();

    public Task<IReadOnlyList<UserSummary>> ListAsync(CancellationToken cancellationToken) => directory.ListAsync(cancellationToken);

    public async Task<IssuedPassword> CreateAsync(string username, string roleCode, CancellationToken cancellationToken)
    {
        if (!AcceptedUsername().IsMatch(username))
        {
            throw new RuleViolation(RuleKind.Invalid, "nom d'utilisateur refusé");
        }
        RequireKnownRole(roleCode);
        var password = TemporaryPassword();
        var user = new NewUser(Guid.CreateVersion7(), username, hasher.Hash(password), roleCode, clock.GetUtcNow());
        if (!await directory.TryCreateAsync(user, cancellationToken).ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.Conflict, "nom d'utilisateur déjà pris");
        }
        return new IssuedPassword(await RequireAsync(user.Id, cancellationToken).ConfigureAwait(false), password);
    }

    public async Task<UserSummary> ChangeRoleAsync(Guid actorId, Guid userId, string roleCode, CancellationToken cancellationToken)
    {
        RequireOther(actorId, userId, "un administrateur ne change pas son propre rôle");
        RequireKnownRole(roleCode);
        await RequireFoundAsync(directory.SetRoleAsync(userId, roleCode, cancellationToken)).ConfigureAwait(false);
        return await RequireAsync(userId, cancellationToken).ConfigureAwait(false);
    }

    public async Task<UserSummary> DisableAsync(Guid actorId, Guid userId, CancellationToken cancellationToken)
    {
        RequireOther(actorId, userId, "un administrateur ne se désactive pas lui-même");
        var now = clock.GetUtcNow();
        await RequireFoundAsync(directory.SetDisabledAtAsync(userId, now, cancellationToken)).ConfigureAwait(false);
        await directory.RevokeSessionsAsync(userId, now, cancellationToken).ConfigureAwait(false);
        return await RequireAsync(userId, cancellationToken).ConfigureAwait(false);
    }

    public async Task<UserSummary> EnableAsync(Guid userId, CancellationToken cancellationToken)
    {
        await RequireFoundAsync(directory.SetDisabledAtAsync(userId, null, cancellationToken)).ConfigureAwait(false);
        return await RequireAsync(userId, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>Nouveau mot de passe provisoire, renvoyé une seule fois ; les sessions du compte sont révoquées.</summary>
    public async Task<IssuedPassword> ResetPasswordAsync(Guid userId, CancellationToken cancellationToken)
    {
        var password = TemporaryPassword();
        await RequireFoundAsync(directory.SetPasswordAsync(userId, hasher.Hash(password), null, cancellationToken)).ConfigureAwait(false);
        await directory.RevokeSessionsAsync(userId, clock.GetUtcNow(), cancellationToken).ConfigureAwait(false);
        return new IssuedPassword(await RequireAsync(userId, cancellationToken).ConfigureAwait(false), password);
    }

    /// <summary>Changement par l'utilisateur lui-même ; toutes ses sessions sont révoquées, il se reconnecte.</summary>
    public async Task ChangeOwnPasswordAsync(Guid userId, string currentPassword, string newPassword, CancellationToken cancellationToken)
    {
        if (newPassword.Length < MinimumPasswordLength || newPassword == currentPassword)
        {
            throw new RuleViolation(RuleKind.Invalid, "nouveau mot de passe refusé");
        }
        var hash = await directory.PasswordHashOfAsync(userId, cancellationToken).ConfigureAwait(false);
        if (hash is null || !hasher.Verify(currentPassword, hash))
        {
            throw new RuleViolation(RuleKind.Invalid, "mot de passe actuel refusé");
        }
        var now = clock.GetUtcNow();
        await directory.SetPasswordAsync(userId, hasher.Hash(newPassword), now, cancellationToken).ConfigureAwait(false);
        await directory.RevokeSessionsAsync(userId, now, cancellationToken).ConfigureAwait(false);
    }

    private async Task<UserSummary> RequireAsync(Guid userId, CancellationToken cancellationToken) =>
        await directory.FindAsync(userId, cancellationToken).ConfigureAwait(false)
        ?? throw new RuleViolation(RuleKind.NotFound, "compte inconnu");

    private static async Task RequireFoundAsync(Task<bool> update)
    {
        if (!await update.ConfigureAwait(false))
        {
            throw new RuleViolation(RuleKind.NotFound, "compte inconnu");
        }
    }

    private static void RequireOther(Guid actorId, Guid userId, string detail)
    {
        if (actorId == userId)
        {
            throw new RuleViolation(RuleKind.Invalid, detail);
        }
    }

    private static void RequireKnownRole(string roleCode)
    {
        if (!IdentityCatalog.Roles.Any(r => r.Code == roleCode))
        {
            throw new RuleViolation(RuleKind.Invalid, "rôle inconnu");
        }
    }

    private static string TemporaryPassword() =>
        Convert.ToBase64String(RandomNumberGenerator.GetBytes(TemporaryPasswordBytes)).TrimEnd('=').Replace('+', '-').Replace('/', '_');
}
