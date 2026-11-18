using System.Net;
using System.Net.Http.Json;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Yarp.ReverseProxy.Forwarder;

namespace Hannibal.Backoffice.Tests;

public sealed class SessionAndRelayTests : IAsyncDisposable
{
    private const string AdminPassword = "mot-de-passe-admin-de-test";
    private const string MissionId = "6f1c1a52-2f4e-4d39-9a0e-1b4ad7c0e001";
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private readonly ManualTime _clock = new();
    private readonly CapturingApi _api = new();
    private readonly WebApplicationFactory<Program> _app;

    public SessionAndRelayTests()
    {
        _app = Backoffice.Create(("INITIAL_ADMIN_PASSWORD", AdminPassword), ("INTERNAL_TOKEN", "jeton-interne-de-test"))
            .WithWebHostBuilder(b => b.ConfigureTestServices(services =>
            {
                services.AddSingleton<TimeProvider>(_clock);
                services.AddSingleton<IForwarderHttpClientFactory>(_api);
            }));
        var store = _app.Services.GetRequiredService<InMemoryIdentityStore>();
        var hasher = _app.Services.GetRequiredService<IPasswordHasher>();
        store.AddUser("olivia", hasher.Hash("operatrice"), RoleCode.Operator);
        store.AddUser("simon", hasher.Hash("superviseur"), RoleCode.Supervisor);
    }

    public async ValueTask DisposeAsync() => await _app.DisposeAsync();

    private async Task<HttpClient> SignedInAsync(string username, string password)
    {
        var client = _app.CreateClient();
        using var response = await client.PostAsJsonAsync("/v1/session", new { username, password }, Ct);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        return client;
    }

    [Fact]
    public async Task Connexion_session_courante_puis_deconnexion()
    {
        var client = _app.CreateClient();
        using var signIn = await client.PostAsJsonAsync("/v1/session", new { username = "admin", password = AdminPassword }, Ct);
        Assert.Equal(HttpStatusCode.OK, signIn.StatusCode);
        var cookie = Assert.Single(signIn.Headers.GetValues("Set-Cookie"));
        Assert.Contains("httponly", cookie, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("samesite=strict", cookie, StringComparison.OrdinalIgnoreCase);
        await Contract.AssertMatchesAsync(signIn, "SessionView");

        using var current = await client.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct);
        var body = await Contract.AssertMatchesAsync(current, "SessionView");
        Assert.Equal(("admin", "admin"), ((string?)body["username"], (string?)body["role"]));
        Assert.Contains("user:manage", body["permissions"]!.AsArray().Select(p => (string?)p));

        using var signOut = await client.DeleteAsync(new Uri("/v1/session", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.NoContent, signOut.StatusCode);
        using var after = await client.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.Unauthorized, after.StatusCode);
        Assert.Equal("unauthenticated", (string?)(await Contract.AssertMatchesAsync(after, "ErrorBody"))["code"]);
    }

    [Theory]
    [InlineData("admin", "mauvais")]
    [InlineData("inconnu", "peu-importe")]
    public async Task Identifiants_refuses_sans_dire_lequel_est_faux(string username, string password)
    {
        using var response = await _app.CreateClient().PostAsJsonAsync("/v1/session", new { username, password }, Ct);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal("Authentification requise.", (string?)(await Contract.AssertMatchesAsync(response, "ErrorBody"))["message"]);
    }

    [Fact]
    public async Task La_session_expire_sans_activite_et_au_bout_de_12_heures()
    {
        var idle = await SignedInAsync("olivia", "operatrice");
        _clock.Advance(SessionPolicy.IdleTimeout + TimeSpan.FromSeconds(1));
        Assert.Equal(HttpStatusCode.Unauthorized, (await idle.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct)).StatusCode);

        var active = await SignedInAsync("olivia", "operatrice");
        var elapsed = TimeSpan.Zero;
        while (elapsed + TimeSpan.FromMinutes(25) < SessionPolicy.AbsoluteTimeout)
        {
            _clock.Advance(TimeSpan.FromMinutes(25));
            elapsed += TimeSpan.FromMinutes(25);
            Assert.Equal(HttpStatusCode.OK, (await active.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct)).StatusCode);
        }
        _clock.Advance(SessionPolicy.AbsoluteTimeout - elapsed);
        Assert.Equal(HttpStatusCode.Unauthorized, (await active.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct)).StatusCode);
    }

    [Fact]
    public async Task Le_relais_transmet_l_identite_de_la_session_et_jamais_celle_du_navigateur()
    {
        var client = await SignedInAsync("olivia", "operatrice");
        using var request = new HttpRequestMessage(HttpMethod.Post, $"/v1/missions/{MissionId}/orders")
        {
            Content = JsonContent.Create(new { text = "ALL SHIPS TURN 30 STBD" }),
        };
        request.Headers.Add("X-Hx-User", "usurpateur");
        request.Headers.Add("X-Internal-Token", "jeton-du-navigateur");

        using var response = await client.SendAsync(request, Ct);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var forwarded = Assert.Single(_api.Requests);
        Assert.Equal($"/v1/missions/{MissionId}/orders", forwarded.Path);
        Assert.Equal(["olivia"], forwarded.Headers["X-Hx-User"]);
        Assert.Equal(["jeton-interne-de-test"], forwarded.Headers["X-Internal-Token"]);
        Assert.False(forwarded.Headers.ContainsKey("Cookie"));
    }

    [Theory]
    [InlineData(null, "GET", "/v1/scenarios", HttpStatusCode.Unauthorized)]
    [InlineData("olivia", "GET", "/v1/scenarios", HttpStatusCode.OK)]
    [InlineData("olivia", "POST", "/v1/commands/" + MissionId + "/decision", HttpStatusCode.Forbidden)]
    [InlineData("simon", "POST", "/v1/commands/" + MissionId + "/decision", HttpStatusCode.OK)]
    [InlineData("olivia", "GET", "/v1/audit?limit=2", HttpStatusCode.Forbidden)]
    [InlineData("simon", "GET", "/v1/audit/integrity", HttpStatusCode.OK)]
    [InlineData("simon", "GET", "/v1/missions/" + MissionId + "/events", HttpStatusCode.OK)]
    [InlineData("olivia", "POST", "/v1/missions/" + MissionId + "/simulations", HttpStatusCode.OK)]
    [InlineData("olivia", "POST", "/v1/missions/" + MissionId + "/requests/alfa/reply", HttpStatusCode.Forbidden)]
    [InlineData("simon", "POST", "/v1/missions/" + MissionId + "/requests/alfa/reply", HttpStatusCode.OK)]
    public async Task Chaque_route_relayee_exige_sa_permission(string? username, string method, string path, HttpStatusCode expected)
    {
        var client = username switch
        {
            "olivia" => await SignedInAsync("olivia", "operatrice"),
            "simon" => await SignedInAsync("simon", "superviseur"),
            _ => _app.CreateClient(),
        };

        using var response = await client.SendAsync(new HttpRequestMessage(new HttpMethod(method), path), Ct);

        Assert.Equal(expected, response.StatusCode);
        Assert.Equal(expected == HttpStatusCode.OK ? 1 : 0, _api.Requests.Count);
        if (expected == HttpStatusCode.OK)
        {
            Assert.Equal(path, _api.Requests[0].Path);
        }
    }

    private sealed class ManualTime : TimeProvider
    {
        private DateTimeOffset _now = new(2026, 11, 18, 8, 0, 0, TimeSpan.Zero);

        public void Advance(TimeSpan by) => _now += by;

        public override DateTimeOffset GetUtcNow() => _now;
    }

    internal sealed record ForwardedRequest(string Path, Dictionary<string, string[]> Headers);

    /// <summary>Remplace <c>apps/api</c> : enregistre ce que YARP lui aurait envoyé et répond <c>200 {}</c>.</summary>
    private sealed class CapturingApi : HttpMessageHandler, IForwarderHttpClientFactory
    {
        public List<ForwardedRequest> Requests { get; } = [];

        public HttpMessageInvoker CreateClient(ForwarderHttpClientContext context) => new(this, disposeHandler: false);

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var headers = request.Headers.ToDictionary(h => h.Key, h => h.Value.ToArray(), StringComparer.OrdinalIgnoreCase);
            Requests.Add(new ForwardedRequest(request.RequestUri!.PathAndQuery, headers));
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = JsonContent.Create(new { }) });
        }
    }
}
