using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Hannibal.Backoffice.Infrastructure.Persistence;
using Hannibal.Backoffice.Infrastructure.Planning;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

namespace Hannibal.Backoffice.Tests;

public sealed class MissionPlanningTests : IAsyncDisposable
{
    private const string AdminPassword = "mot-de-passe-admin-de-test";
    private const string Path = "/v1/planning/missions";
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private readonly WebApplicationFactory<Program> _app;
    private readonly Guid _olivia;

    public MissionPlanningTests()
    {
        _app = Backoffice.Create(("INITIAL_ADMIN_PASSWORD", AdminPassword));
        var hasher = _app.Services.GetRequiredService<IPasswordHasher>();
        _olivia = _app.Services.GetRequiredService<InMemoryIdentityStore>().AddUser("olivia", hasher.Hash("operatrice"), RoleCode.Operator).Id;
    }

    public async ValueTask DisposeAsync() => await _app.DisposeAsync();

    private InMemoryMissionRunner Runner => _app.Services.GetRequiredService<InMemoryMissionRunner>();

    private async Task<HttpClient> SignedInAsync(string username, string password)
    {
        var client = _app.CreateClient();
        using var response = await client.PostAsJsonAsync("/v1/session", new { username, password }, Ct);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        return client;
    }

    private object Plan(string playerShip = "hannibal", string gameRole = "guide") => new
    {
        scenario_id = "contact_inconnu",
        player_ship = playerShip,
        autopilot = true,
        participants = new[] { new { user_id = _olivia, ship = "hannibal", game_role = gameRole } },
    };

    private static async Task<JsonNode> PostAsync(HttpClient client, string path, object? body, HttpStatusCode expected, string schema = "PlannedMission")
    {
        using var response = await client.PostAsJsonAsync(path, body, Ct);
        Assert.Equal(expected, response.StatusCode);
        return await Contract.AssertMatchesAsync(response, expected is HttpStatusCode.OK or HttpStatusCode.Created ? schema : "ErrorBody");
    }

    [Fact]
    public async Task Planifier_puis_lancer_envoie_la_photo_une_seule_fois()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        var planned = await PostAsync(admin, Path, Plan(), HttpStatusCode.Created);
        Assert.Equal("planned", (string?)planned["state"]);
        Assert.Equal(1, (int?)planned["scenario_version"]);
        var id = (string)planned["id"]!;

        Assert.Equal("ready", (string?)(await PostAsync(admin, $"{Path}/{id}/ready", null, HttpStatusCode.OK))["state"]);
        var launched = await PostAsync(admin, $"{Path}/{id}/launch", null, HttpStatusCode.OK);
        Assert.Equal("running", (string?)launched["state"]);
        Assert.Equal("running", (string?)launched["run_phase"]);
        await PostAsync(admin, $"{Path}/{id}/launch", null, HttpStatusCode.OK);

        var snapshot = Assert.Single(Runner.Snapshots).Value;
        Assert.Equal("olivia", snapshot.Operator);
        Assert.Equal("hannibal", snapshot.PlayerShip);
        Assert.True(snapshot.Autopilot);
        Assert.Equal(["hannibal", "alfa", "charlie", "delta"], snapshot.Ships.Select(s => s.CallSign));
        Assert.All(snapshot.Ships, s => Assert.True(s.MaxSpeedKnots > s.MinSpeedKnots));
        Assert.Equal("contact_inconnu", (string?)JsonNode.Parse(snapshot.ScenarioJson)!["id"]);
    }

    [Fact]
    public async Task Navire_hors_flotte_ou_role_inconnu_sont_refuses()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        await PostAsync(admin, Path, Plan(playerShip: "zulu"), HttpStatusCode.UnprocessableEntity);
        await PostAsync(admin, Path, Plan(gameRole: "pirate"), HttpStatusCode.UnprocessableEntity);
    }

    [Fact]
    public async Task Une_operatrice_joue_mais_ne_planifie_pas()
    {
        var olivia = await SignedInAsync("olivia", "operatrice");
        using var scenarios = await olivia.GetAsync(new Uri("/v1/scenarios", UriKind.Relative), Ct);
        Assert.Equal(HttpStatusCode.OK, scenarios.StatusCode);
        var list = await Contract.AssertEachMatchesAsync(scenarios, "ScenarioSummary");
        Assert.Contains("contact_inconnu", list.Select(s => (string?)s!["id"]));

        using var plan = await olivia.PostAsJsonAsync(Path, Plan(), Ct);
        Assert.Equal(HttpStatusCode.Forbidden, plan.StatusCode);
    }

    [Fact]
    public async Task L_historique_est_pagine_et_montre_le_deroule()
    {
        var admin = await SignedInAsync("admin", AdminPassword);
        var ids = new List<string>();
        for (var i = 0; i < 3; i++)
        {
            ids.Add((string)(await PostAsync(admin, Path, Plan(), HttpStatusCode.Created))["id"]!);
        }
        await PostAsync(admin, $"{Path}/{ids[0]}/launch", null, HttpStatusCode.OK);
        Runner.Finish(Guid.Parse(ids[0]));

        using var first = await admin.GetAsync(new Uri($"{Path}?limit=2", UriKind.Relative), Ct);
        var page = await Contract.AssertMatchesAsync(first, "MissionHistory");
        Assert.Equal(2, page["missions"]!.AsArray().Count);
        var cursor = (string)page["next_cursor"]!;

        using var second = await admin.GetAsync(new Uri($"{Path}?limit=2&cursor={cursor}", UriKind.Relative), Ct);
        var rest = await Contract.AssertMatchesAsync(second, "MissionHistory");
        Assert.Null((string?)rest["next_cursor"]);
        var seen = page["missions"]!.AsArray().Concat(rest["missions"]!.AsArray()).ToList();
        Assert.Equal(ids.Order(), seen.Select(m => (string)m!["id"]!).Order());
        var played = seen.Single(m => (string?)m!["id"] == ids[0])!;
        Assert.Equal("finished", (string?)played["run_phase"]);

        Assert.Equal("archived", (string?)(await PostAsync(admin, $"{Path}/{ids[0]}/archive", null, HttpStatusCode.OK))["state"]);
    }
}
