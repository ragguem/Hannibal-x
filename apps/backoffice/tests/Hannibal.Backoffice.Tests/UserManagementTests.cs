using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

namespace Hannibal.Backoffice.Tests;

public sealed class UserManagementTests : IAsyncDisposable
{
    private const string AdminPassword = "mot-de-passe-admin-de-test";
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private readonly WebApplicationFactory<Program> _app;

    public UserManagementTests()
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

    private static async Task<JsonNode> CreateAsync(HttpClient admin, string username, string role)
    {
        using var response = await admin.PostAsJsonAsync("/v1/users", new { username, role }, Ct);
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        return await Contract.AssertMatchesAsync(response, "IssuedPassword");
    }

    private static async Task<string> ErrorCodeAsync(HttpResponseMessage response) =>
        (string)(await Contract.AssertMatchesAsync(response, "ErrorBody"))["code"]!;

    [Fact]
    public async Task Compte_cree_avec_mot_de_passe_provisoire_que_l_utilisateur_remplace()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        var issued = await CreateAsync(admin, "marin.duval", RoleCode.Operator);
        Assert.Null(issued["user"]!["password_changed_at"]);

        var marin = await SignedInAsync("marin.duval", (string)issued["temporary_password"]!);
        using var change = await marin.PutAsJsonAsync(
            "/v1/session/password", new { current_password = (string)issued["temporary_password"]!, new_password = "nouveau-mot-de-passe" }, Ct);
        Assert.Equal(HttpStatusCode.NoContent, change.StatusCode);
        using var afterChange = await marin.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.Unauthorized, afterChange.StatusCode);

        await SignedInAsync("marin.duval", "nouveau-mot-de-passe");
        using var list = await admin.GetAsync(new Uri("/v1/users", UriKind.Relative), Ct);
        var users = (await Contract.AssertMatchesAsync(list, "UserList"))["users"]!.AsArray();
        Assert.Equal(["admin", "marin.duval", "olivia"], users.Select(u => (string?)u!["username"]));
        Assert.NotNull(users.Single(u => (string?)u!["username"] == "marin.duval")!["password_changed_at"]);
    }

    [Fact]
    public async Task Desactiver_coupe_les_sessions_et_la_connexion_reactiver_les_rend()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        var olivia = await SignedInAsync("olivia", "operatrice");
        using var list = await admin.GetAsync(new Uri("/v1/users", UriKind.Relative), Ct);
        var id = (string)(await Contract.AssertMatchesAsync(list, "UserList"))["users"]!.AsArray()
            .Single(u => (string?)u!["username"] == "olivia")!["id"]!;

        using var disable = await admin.PostAsync(new Uri($"/v1/users/{id}/disable", UriKind.Relative), null, Ct);
        Assert.NotNull((await Contract.AssertMatchesAsync(disable, "UserView"))["disabled_at"]);
        using var revoked = await olivia.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.Unauthorized, revoked.StatusCode);
        using var refused = await _app.CreateClient().PostAsJsonAsync("/v1/session", new { username = "olivia", password = "operatrice" }, Ct);
        Assert.Equal(HttpStatusCode.Unauthorized, refused.StatusCode);

        using var enable = await admin.PostAsync(new Uri($"/v1/users/{id}/enable", UriKind.Relative), null, Ct);
        Assert.Null((await Contract.AssertMatchesAsync(enable, "UserView"))["disabled_at"]);
        await SignedInAsync("olivia", "operatrice");
    }

    [Fact]
    public async Task Reinitialiser_donne_un_nouveau_provisoire_et_revoque_les_sessions()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        var created = await CreateAsync(admin, "lea.martin", RoleCode.Supervisor);
        var lea = await SignedInAsync("lea.martin", (string)created["temporary_password"]!);

        using var reset = await admin.PostAsync(new Uri($"/v1/users/{created["user"]!["id"]}/password-reset", UriKind.Relative), null, Ct);
        var issued = await Contract.AssertMatchesAsync(reset, "IssuedPassword");

        Assert.NotEqual((string?)created["temporary_password"], (string?)issued["temporary_password"]);
        using var revoked = await lea.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.Unauthorized, revoked.StatusCode);
        await SignedInAsync("lea.martin", (string)issued["temporary_password"]!);
    }

    [Fact]
    public async Task Changer_de_role_change_les_permissions_de_la_session()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        var created = await CreateAsync(admin, "hugo.bernard", RoleCode.Operator);
        var hugo = await SignedInAsync("hugo.bernard", (string)created["temporary_password"]!);

        using var change = await admin.PutAsJsonAsync($"/v1/users/{created["user"]!["id"]}/role", new { role = RoleCode.Supervisor }, Ct);
        Assert.Equal(RoleCode.Supervisor, (string?)(await Contract.AssertMatchesAsync(change, "UserView"))["role"]);

        using var session = await hugo.GetAsync(new Uri("/v1/session", UriKind.Relative), Ct);
        var permissions = (await Contract.AssertMatchesAsync(session, "SessionView"))["permissions"]!.AsArray().Select(p => (string?)p);
        Assert.Contains(Permission.CommandDecide, permissions);
    }

    [Fact]
    public async Task Regles_refusees_avec_un_code_stable()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        using var session = await admin.GetAsync(new Uri("/v1/users", UriKind.Relative), Ct);
        var adminId = (string)(await Contract.AssertMatchesAsync(session, "UserList"))["users"]!.AsArray()
            .Single(u => (string?)u!["username"] == "admin")!["id"]!;

        using var duplicate = await admin.PostAsJsonAsync("/v1/users", new { username = "olivia", role = RoleCode.Operator }, Ct);
        Assert.Equal((HttpStatusCode.Conflict, "conflict"), (duplicate.StatusCode, await ErrorCodeAsync(duplicate)));

        using var badRole = await admin.PostAsJsonAsync("/v1/users", new { username = "nouveau", role = "amiral" }, Ct);
        Assert.Equal((HttpStatusCode.UnprocessableEntity, "invalid_request"), (badRole.StatusCode, await ErrorCodeAsync(badRole)));

        using var badName = await admin.PostAsJsonAsync("/v1/users", new { username = "Nom Avec Espaces", role = RoleCode.Operator }, Ct);
        Assert.Equal(HttpStatusCode.UnprocessableEntity, badName.StatusCode);

        using var selfDisable = await admin.PostAsync(new Uri($"/v1/users/{adminId}/disable", UriKind.Relative), null, Ct);
        Assert.Equal((HttpStatusCode.UnprocessableEntity, "invalid_request"), (selfDisable.StatusCode, await ErrorCodeAsync(selfDisable)));

        using var selfDemote = await admin.PutAsJsonAsync($"/v1/users/{adminId}/role", new { role = RoleCode.Operator }, Ct);
        Assert.Equal(HttpStatusCode.UnprocessableEntity, selfDemote.StatusCode);

        using var unknown = await admin.PostAsync(new Uri($"/v1/users/{Guid.CreateVersion7()}/enable", UriKind.Relative), null, Ct);
        Assert.Equal((HttpStatusCode.NotFound, "not_found"), (unknown.StatusCode, await ErrorCodeAsync(unknown)));

        using var shortPassword = await admin.PutAsJsonAsync("/v1/session/password", new { current_password = AdminPassword, new_password = "court" }, Ct);
        Assert.Equal(HttpStatusCode.UnprocessableEntity, shortPassword.StatusCode);
    }

    [Fact]
    public async Task Un_operateur_ne_gere_pas_les_comptes()
    {
        var olivia = await SignedInAsync("olivia", "operatrice");

        using var list = await olivia.GetAsync(new Uri("/v1/users", UriKind.Relative), Ct);
        using var roles = await olivia.GetAsync(new Uri("/v1/roles", UriKind.Relative), Ct);
        using var anonymous = await _app.CreateClient().GetAsync(new Uri("/v1/users", UriKind.Relative), Ct);

        Assert.Equal((HttpStatusCode.Forbidden, "forbidden"), (list.StatusCode, await ErrorCodeAsync(list)));
        Assert.Equal(HttpStatusCode.Forbidden, roles.StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, anonymous.StatusCode);
    }

    [Fact]
    public async Task Les_roles_sont_ceux_du_catalogue()
    {
        var admin = await SignedInAsync("admin", AdminPassword);

        using var response = await admin.GetAsync(new Uri("/v1/roles", UriKind.Relative), Ct);
        var roles = (await Contract.AssertMatchesAsync(response, "RoleList"))["roles"]!.AsArray();

        Assert.Equal(IdentityCatalog.Roles.Select(r => r.Code), roles.Select(r => (string?)r!["code"]));
    }
}
