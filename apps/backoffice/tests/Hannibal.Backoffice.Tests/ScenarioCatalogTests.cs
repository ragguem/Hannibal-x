using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Catalog;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

namespace Hannibal.Backoffice.Tests;

public sealed class ScenarioCatalogTests : IAsyncDisposable
{
    private const string AdminPassword = "mot-de-passe-admin-de-test";
    private const string Path = "/v1/catalog/scenarios";
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private static readonly string ChangementFormation =
        YamlScenarioDocuments.RepositoryScenarios().Single(y => y.Contains("id: changement_formation", StringComparison.Ordinal));

    private readonly WebApplicationFactory<Program> _app;

    public ScenarioCatalogTests()
    {
        _app = Backoffice.Create(("INITIAL_ADMIN_PASSWORD", AdminPassword));
        var hasher = _app.Services.GetRequiredService<IPasswordHasher>();
        _app.Services.GetRequiredService<InMemoryIdentityStore>().AddUser("olivia", hasher.Hash("operatrice"), RoleCode.Operator);
    }

    public async ValueTask DisposeAsync() => await _app.DisposeAsync();

    private async Task<HttpClient> SignedInAsync(string username, string password)
    {
        var client = _app.CreateClient();
        using var response = await client.PostAsJsonAsync("/v1/session", new { username, password }, Ct);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        return client;
    }

    private static async Task<JsonNode> ImportAsync(HttpClient admin, string yaml, HttpStatusCode expected = HttpStatusCode.Created)
    {
        using var response = await admin.PostAsJsonAsync(Path, new { yaml }, Ct);
        Assert.Equal(expected, response.StatusCode);
        return await Contract.AssertMatchesAsync(response, expected == HttpStatusCode.Created ? "ScenarioEntry" : "ErrorBody");
    }

    [Fact]
    public async Task Les_scenarios_du_depot_sont_semes_et_publies()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        using var response = await admin.GetAsync(new Uri(Path, UriKind.Relative), Ct);
        var scenarios = (await Contract.AssertMatchesAsync(response, "ScenarioCatalogList"))["scenarios"]!.AsArray();
        Assert.Equal(
            ["changement_formation", "contact_inconnu", "exercice_formations", "interception_hostile", "menace_ennemie", "transit_colonne"],
            scenarios.Select(s => (string?)s!["id"]));
        Assert.All(scenarios, s => Assert.Equal(1, (int?)s!["published_version"]));
    }

    [Fact]
    public async Task Import_cree_une_version_et_un_reimport_identique_ne_change_rien()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        var changed = ChangementFormation.Replace("duree_s: 360", "duree_s: 400", StringComparison.Ordinal);

        var first = await ImportAsync(admin, changed);
        Assert.Equal(2, (int?)first["latest_version"]);
        Assert.Equal(1, (int?)first["published_version"]);

        var again = await ImportAsync(admin, changed);
        Assert.Equal(2, (int?)again["latest_version"]);

        using var exported = await admin.GetAsync(new Uri($"{Path}/changement_formation/versions/2/yaml", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.OK, exported.StatusCode);
        Assert.Equal(changed, await exported.Content.ReadAsStringAsync(Ct));
    }

    [Fact]
    public async Task Flotte_hors_catalogue_ou_document_non_conforme_sont_refuses()
    {
        var admin = await SignedInAsync("admin", AdminPassword);

        var fleet = await ImportAsync(admin, ChangementFormation.Replace("nom: delta", "nom: zulu", StringComparison.Ordinal), HttpStatusCode.UnprocessableEntity);
        Assert.Contains("zulu", (string)fleet["message"]!, StringComparison.Ordinal);

        var schema = await ImportAsync(admin, ChangementFormation.Replace("duree_s: 360", "duree_s: longue", StringComparison.Ordinal), HttpStatusCode.UnprocessableEntity);
        Assert.Contains("duree_s", (string)schema["message"]!, StringComparison.Ordinal);

        var garbage = await ImportAsync(admin, "id: [", HttpStatusCode.UnprocessableEntity);
        Assert.Equal("invalid_request", (string?)garbage["code"]);
    }

    [Fact]
    public async Task Publication_puis_archivage_bloque_les_imports()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        await ImportAsync(admin, ChangementFormation.Replace("duree_s: 360", "duree_s: 400", StringComparison.Ordinal));

        using var published = await admin.PostAsJsonAsync($"{Path}/changement_formation/publish", new { version = 2 }, Ct);
        Assert.Equal(2, (int?)(await Contract.AssertMatchesAsync(published, "ScenarioEntry"))["published_version"]);

        using var unknown = await admin.PostAsJsonAsync($"{Path}/changement_formation/publish", new { version = 9 }, Ct);
        Assert.Equal(HttpStatusCode.UnprocessableEntity, unknown.StatusCode);

        using var archived = await admin.PostAsync(new Uri($"{Path}/changement_formation/archive", UriKind.Relative), null, Ct);
        Assert.NotNull((await Contract.AssertMatchesAsync(archived, "ScenarioEntry"))["archived_at"]);

        var refused = await ImportAsync(admin, ChangementFormation.Replace("duree_s: 360", "duree_s: 420", StringComparison.Ordinal), HttpStatusCode.Conflict);
        Assert.Equal("conflict", (string?)refused["code"]);
    }

    [Fact]
    public async Task Le_catalogue_des_scenarios_exige_catalog_manage()
    {
        using var anonymous = await _app.CreateClient().GetAsync(new Uri(Path, UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.Unauthorized, anonymous.StatusCode);

        var operatrice = await SignedInAsync("olivia", "operatrice");
        using var forbidden = await operatrice.PostAsJsonAsync(Path, new { yaml = ChangementFormation }, Ct);
        Assert.Equal(HttpStatusCode.Forbidden, forbidden.StatusCode);
    }
}
