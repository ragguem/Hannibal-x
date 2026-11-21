using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Catalog;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

namespace Hannibal.Backoffice.Tests;

public sealed class ShipCatalogTests : IAsyncDisposable
{
    private const string AdminPassword = "mot-de-passe-admin-de-test";
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private readonly WebApplicationFactory<Program> _app;

    public ShipCatalogTests()
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

    private static async Task<JsonArray> ShipsAsync(HttpClient admin)
    {
        using var response = await admin.GetAsync(new Uri("/v1/ships", UriKind.Relative), Ct);
        return (await Contract.AssertMatchesAsync(response, "ShipList"))["ships"]!.AsArray();
    }

    private static async Task<string> ErrorCodeAsync(HttpResponseMessage response) =>
        (string)(await Contract.AssertMatchesAsync(response, "ErrorBody"))["code"]!;

    private static object Class(string code, int min = 4, int max = 30) =>
        new { code, label = "Corvette", min_speed_knots = min, max_speed_knots = max, turn_radius_meters = 350.0, length_meters = 95.0 };

    [Fact]
    public async Task Le_catalogue_seme_porte_les_navires_des_scenarios()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        using var classes = await admin.GetAsync(new Uri("/v1/ship-classes", UriKind.Relative), Ct);
        var codes = (await Contract.AssertMatchesAsync(classes, "ShipClassList"))["classes"]!.AsArray().Select(c => (string?)c!["code"]);
        Assert.Equal(ShipCatalogSeed.Classes.Select(c => c.Code).Order(StringComparer.Ordinal), codes);

        var ships = await ShipsAsync(admin);
        Assert.Equal(["alfa", "charlie", "delta", "hannibal"], ships.Select(s => (string?)s!["call_sign"]));
        Assert.All(ships, s => Assert.True((bool)s!["active"]!));
    }

    [Fact]
    public async Task Classe_creee_puis_modifiee_et_navire_rattache()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        using var created = await admin.PostAsJsonAsync("/v1/ship-classes", Class("corvette"), Ct);
        Assert.Equal(HttpStatusCode.Created, created.StatusCode);
        await Contract.AssertMatchesAsync(created, "ShipClass");

        using var updated = await admin.PutAsJsonAsync(
            "/v1/ship-classes/corvette",
            new { label = "  Corvette légère ", min_speed_knots = 5, max_speed_knots = 26, turn_radius_meters = 300.0, length_meters = 90.0 },
            Ct);
        var view = await Contract.AssertMatchesAsync(updated, "ShipClass");
        Assert.Equal("Corvette légère", (string?)view["label"]);
        Assert.Equal(26, (int)view["max_speed_knots"]!);

        using var ship = await admin.PostAsJsonAsync("/v1/ships", new { call_sign = "echo", class_code = "corvette" }, Ct);
        Assert.Equal(HttpStatusCode.Created, ship.StatusCode);
        var echo = await Contract.AssertMatchesAsync(ship, "ShipView");
        Assert.Equal("corvette", (string?)echo["class_code"]);

        using var moved = await admin.PutAsJsonAsync($"/v1/ships/{echo["id"]}/class", new { class_code = "aviso" }, Ct);
        Assert.Equal("aviso", (string?)(await Contract.AssertMatchesAsync(moved, "ShipView"))["class_code"]);
    }

    [Fact]
    public async Task Navire_retire_puis_remis_en_service()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        var delta = (await ShipsAsync(admin)).Single(s => (string?)s!["call_sign"] == "delta")!;

        using var retired = await admin.PostAsync(new Uri($"/v1/ships/{delta["id"]}/retire", UriKind.Relative), null, Ct);
        var view = await Contract.AssertMatchesAsync(retired, "ShipView");
        Assert.False((bool)view["active"]!);
        Assert.NotNull(view["retired_at"]);

        using var back = await admin.PostAsync(new Uri($"/v1/ships/{delta["id"]}/reactivate", UriKind.Relative), null, Ct);
        Assert.True((bool)(await Contract.AssertMatchesAsync(back, "ShipView"))["active"]!);
    }

    [Fact]
    public async Task Les_regles_du_catalogue_renvoient_des_codes_stables()
    {
        var admin = await SignedInAsync("admin", AdminPassword);

        using (var inverted = await admin.PostAsJsonAsync("/v1/ship-classes", Class("lente", min: 20, max: 10), Ct))
        {
            Assert.Equal(HttpStatusCode.UnprocessableEntity, inverted.StatusCode);
            Assert.Equal("invalid_request", await ErrorCodeAsync(inverted));
        }
        using (var taken = await admin.PostAsJsonAsync("/v1/ship-classes", Class("aviso"), Ct))
        {
            Assert.Equal(HttpStatusCode.Conflict, taken.StatusCode);
        }
        using (var unknownClass = await admin.PutAsJsonAsync(
            "/v1/ship-classes/inconnue",
            new { label = "X", min_speed_knots = 3, max_speed_knots = 20, turn_radius_meters = 300.0, length_meters = 80.0 },
            Ct))
        {
            Assert.Equal(HttpStatusCode.NotFound, unknownClass.StatusCode);
        }
        using (var badCallSign = await admin.PostAsJsonAsync("/v1/ships", new { call_sign = "Echo 1", class_code = "aviso" }, Ct))
        {
            Assert.Equal(HttpStatusCode.UnprocessableEntity, badCallSign.StatusCode);
        }
        using (var noClass = await admin.PostAsJsonAsync("/v1/ships", new { call_sign = "echo", class_code = "inconnue" }, Ct))
        {
            Assert.Equal(HttpStatusCode.UnprocessableEntity, noClass.StatusCode);
        }
        using (var duplicate = await admin.PostAsJsonAsync("/v1/ships", new { call_sign = "alfa", class_code = "aviso" }, Ct))
        {
            Assert.Equal(HttpStatusCode.Conflict, duplicate.StatusCode);
            Assert.Equal("conflict", await ErrorCodeAsync(duplicate));
        }
        using var unknownShip = await admin.PostAsync(new Uri($"/v1/ships/{Guid.NewGuid()}/retire", UriKind.Relative), null, Ct);
        Assert.Equal(HttpStatusCode.NotFound, unknownShip.StatusCode);
    }

    [Fact]
    public async Task Catalogue_reserve_a_catalog_manage()
    {
        var operatrice = await SignedInAsync("olivia", "operatrice");
        using var forbidden = await operatrice.GetAsync(new Uri("/v1/ships", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.Forbidden, forbidden.StatusCode);

        using var anonymous = await _app.CreateClient().GetAsync(new Uri("/v1/ship-classes", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.Unauthorized, anonymous.StatusCode);
    }
}
