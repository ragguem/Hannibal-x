using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Seeding.Seeders;

namespace Hannibal.Backoffice.Tests;

public sealed class IdentityCacheTests
{
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private readonly SteppedClock _clock = new();
    private readonly CountingIdentityStore _database;
    private readonly Sessions _sessions;

    public IdentityCacheTests()
    {
        var hasher = new PlainHasher();
        var store = new InMemoryIdentityStore(hasher, new InitialAdminOptions("admin", null));
        store.AddUser("olivia", hasher.Hash("operatrice"), RoleCode.Operator);
        _database = new CountingIdentityStore(store);
        _sessions = new Sessions(new CachedIdentityStore(_database, new IdentityCache(_clock)), hasher, _clock);
    }

    [Fact]
    public async Task Les_requetes_d_une_meme_minute_ne_lisent_ni_n_ecrivent_la_base()
    {
        var signedIn = await _sessions.SignInAsync("olivia", "operatrice", Ct);
        Assert.NotNull(signedIn);

        for (var request = 0; request < 20; request++)
        {
            _clock.Advance(TimeSpan.FromSeconds(1));
            Assert.NotNull(await _sessions.AuthenticateAsync(signedIn.Token, Ct));
        }

        Assert.Equal((1, 0, 1), (_database.SessionReads, _database.Extensions, _database.PermissionReads));
    }

    [Fact]
    public async Task La_session_est_prolongee_au_plus_une_fois_par_minute_et_relue_apres_30_secondes()
    {
        var signedIn = await _sessions.SignInAsync("olivia", "operatrice", Ct);

        _clock.Advance(SessionPolicy.ExtensionInterval + TimeSpan.FromSeconds(5));
        var extended = await _sessions.AuthenticateAsync(signedIn!.Token, Ct);
        _clock.Advance(TimeSpan.FromSeconds(10));
        var cached = await _sessions.AuthenticateAsync(signedIn.Token, Ct);

        Assert.Equal(1, _database.Extensions);
        Assert.Equal(extended!.ExpiresAt, cached!.ExpiresAt);

        _clock.Advance(IdentityCache.SessionLifetime);
        Assert.NotNull(await _sessions.AuthenticateAsync(signedIn.Token, Ct));
        Assert.Equal(2, _database.SessionReads);
    }

    [Fact]
    public async Task Une_deconnexion_est_refusee_tout_de_suite_sur_l_instance()
    {
        var signedIn = await _sessions.SignInAsync("olivia", "operatrice", Ct);
        Assert.NotNull(await _sessions.AuthenticateAsync(signedIn!.Token, Ct));

        await _sessions.SignOutAsync(signedIn.Token, Ct);

        Assert.Null(await _sessions.AuthenticateAsync(signedIn.Token, Ct));
    }

    private sealed class CountingIdentityStore(IIdentityStore inner) : IIdentityStore
    {
        public int SessionReads { get; private set; }

        public int Extensions { get; private set; }

        public int PermissionReads { get; private set; }

        public Task<UserCredentials?> FindActiveUserAsync(string username, CancellationToken cancellationToken) =>
            inner.FindActiveUserAsync(username, cancellationToken);

        public Task<IReadOnlySet<string>> PermissionsOfAsync(string roleCode, CancellationToken cancellationToken)
        {
            PermissionReads++;
            return inner.PermissionsOfAsync(roleCode, cancellationToken);
        }

        public Task CreateSessionAsync(NewSession session, CancellationToken cancellationToken) =>
            inner.CreateSessionAsync(session, cancellationToken);

        public Task<ActiveSession?> FindSessionAsync(byte[] tokenHash, CancellationToken cancellationToken)
        {
            SessionReads++;
            return inner.FindSessionAsync(tokenHash, cancellationToken);
        }

        public Task ExtendSessionAsync(Guid sessionId, DateTimeOffset expiresAt, CancellationToken cancellationToken)
        {
            Extensions++;
            return inner.ExtendSessionAsync(sessionId, expiresAt, cancellationToken);
        }

        public Task RevokeSessionAsync(byte[] tokenHash, DateTimeOffset revokedAt, CancellationToken cancellationToken) =>
            inner.RevokeSessionAsync(tokenHash, revokedAt, cancellationToken);
    }

    private sealed class PlainHasher : IPasswordHasher
    {
        public string Hash(string password) => "plain:" + password;

        public bool Verify(string password, string hash) => hash == "plain:" + password;
    }

    private sealed class SteppedClock : TimeProvider
    {
        private DateTimeOffset _now = new(2026, 11, 21, 8, 0, 0, TimeSpan.Zero);

        public override DateTimeOffset GetUtcNow() => _now;

        public void Advance(TimeSpan by) => _now += by;
    }
}
