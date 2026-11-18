using System.Net;
using System.Net.Http.Headers;

namespace Hannibal.Backoffice.Tests;

public sealed class SystemEndpointsTests
{
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    [Fact]
    public async Task Health_respecte_le_contrat()
    {
        await using var app = Backoffice.Create();
        using var response = await app.CreateClient().GetAsync(new Uri("/v1/health", UriKind.Relative), Ct);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await Contract.AssertMatchesAsync(response, "Health");
        Assert.Equal("backoffice", (string?)body["service"]);
        Assert.Equal("0.2.0", (string?)body["version"]);
    }

    [Fact]
    public async Task Ready_avec_adaptateurs_faux()
    {
        await using var app = Backoffice.Create();
        using var response = await app.CreateClient().GetAsync(new Uri("/v1/ready", UriKind.Relative), Ct);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await Contract.AssertMatchesAsync(response, "Readiness");
        Assert.Equal("ready", (string?)body["status"]);
        Assert.Equal(2, body["dependencies"]!.AsArray().Count);
    }

    [Fact]
    public async Task Ready_degrade_si_les_dependances_reelles_ne_repondent_pas()
    {
        await using var app = Backoffice.Create(
            ("ADAPTERS", "real"),
            ("DATABASE_URL", "Host=127.0.0.1;Port=1;Username=x;Password=x;Timeout=1"),
            ("API_URL", "http://127.0.0.1:1"));
        using var response = await app.CreateClient().GetAsync(new Uri("/v1/ready", UriKind.Relative), Ct);

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        var body = await Contract.AssertMatchesAsync(response, "Readiness");
        Assert.Equal("degraded", (string?)body["status"]);
        Assert.All(body["dependencies"]!.AsArray(), d => Assert.Equal("down", (string?)d!["state"]));
    }

    [Fact]
    public void Adaptateurs_reels_sans_configuration_refuses_au_demarrage()
    {
        using var app = Backoffice.Create(("ADAPTERS", "real"));
        Assert.Throws<InvalidOperationException>(() => app.CreateClient());
    }

    [Fact]
    public async Task Request_id_repris_ou_cree()
    {
        await using var app = Backoffice.Create();
        var client = app.CreateClient();

        using var request = new HttpRequestMessage(HttpMethod.Get, "/v1/health");
        request.Headers.Add("X-Request-Id", "abc-12345678");
        using var echoed = await client.SendAsync(request, Ct);
        using var created = await client.GetAsync(new Uri("/v1/health", UriKind.Relative), Ct);

        Assert.Equal("abc-12345678", echoed.Headers.GetValues("x-request-id").Single());
        Assert.Matches("^[0-9a-f]{32}$", created.Headers.GetValues("x-request-id").Single());
    }

    [Fact]
    public async Task Route_inconnue_renvoie_un_ErrorBody()
    {
        await using var app = Backoffice.Create();
        using var response = await app.CreateClient().GetAsync(new Uri("/v1/inconnue", UriKind.Relative), Ct);

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        var body = await Contract.AssertMatchesAsync(response, "ErrorBody");
        Assert.Equal("http_error", (string?)body["code"]);
        Assert.Equal(response.Headers.GetValues("x-request-id").Single(), (string?)body["request_id"]);
    }

    [Theory]
    [InlineData(null, HttpStatusCode.Unauthorized, "unauthenticated")]
    [InlineData("faux", HttpStatusCode.Forbidden, "forbidden")]
    public async Task Metrics_refuse_sans_le_bon_jeton(string? token, HttpStatusCode expected, string code)
    {
        await using var app = Backoffice.Create(("METRICS_TOKEN", "secret"));
        var client = app.CreateClient();
        if (token is not null)
        {
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        }
        using var response = await client.GetAsync(new Uri("/metrics", UriKind.Relative), Ct);

        Assert.Equal(expected, response.StatusCode);
        var body = await Contract.AssertMatchesAsync(response, "ErrorBody");
        Assert.Equal(code, (string?)body["code"]);
    }

    [Fact]
    public async Task Metrics_avec_le_bon_jeton()
    {
        await using var app = Backoffice.Create(("METRICS_TOKEN", "secret"));
        var client = app.CreateClient();
        await client.GetAsync(new Uri("/v1/health", UriKind.Relative), Ct);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", "secret");
        using var response = await client.GetAsync(new Uri("/metrics", UriKind.Relative), Ct);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("http_requests_received_total", await response.Content.ReadAsStringAsync(Ct), StringComparison.Ordinal);
    }

    [Fact]
    public async Task Metrics_sans_jeton_configure_refuse_hors_local()
    {
        await using var app = Backoffice.Create(("ENVIRONMENT", "production"));
        using var response = await app.CreateClient().GetAsync(new Uri("/metrics", UriKind.Relative), Ct);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }
}
