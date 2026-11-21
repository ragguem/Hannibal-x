namespace Hannibal.Backoffice.Domain.Identity;

public sealed record AuthenticatedUser(Guid Id, string Username, string RoleCode, IReadOnlySet<string> Permissions)
{
    public bool Can(string permission) => Permissions.Contains(permission);
}

/// <summary>Une session expire après 30 min sans activité, et dans tous les cas 12 h après la connexion.</summary>
public static class SessionPolicy
{
    public static readonly TimeSpan IdleTimeout = TimeSpan.FromMinutes(30);
    public static readonly TimeSpan AbsoluteTimeout = TimeSpan.FromHours(12);

    /// <summary>Une prolongation plus courte n'est pas écrite : au plus une écriture par minute et par session.</summary>
    public static readonly TimeSpan ExtensionInterval = TimeSpan.FromMinutes(1);

    public static DateTimeOffset NextExpiry(DateTimeOffset now, DateTimeOffset absoluteExpiresAt) =>
        now + IdleTimeout < absoluteExpiresAt ? now + IdleTimeout : absoluteExpiresAt;
}
