using System.Collections.Concurrent;
using System.Text.Json;
using System.Text.Json.Nodes;
using Json.Schema;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;

namespace Hannibal.Backoffice.Tests;

internal static class Backoffice
{
    public static WebApplicationFactory<Program> Create(params (string Key, string Value)[] settings) =>
        new WebApplicationFactory<Program>().WithWebHostBuilder(b =>
        {
            b.UseSetting("HX_BACKOFFICE_ENVIRONMENT", "test");
            b.UseSetting("HX_BACKOFFICE_ADAPTERS", "fake");
            foreach (var (key, value) in settings)
            {
                b.UseSetting("HX_BACKOFFICE_" + key, value);
            }
        });
}

/// <summary>Valide une réponse contre le schéma exporté par `packages/contracts` (même source que le code Python).</summary>
internal static class Contract
{
    private static readonly ConcurrentDictionary<string, Lazy<JsonSchema>> Schemas = new();

    public static async Task<JsonNode> AssertMatchesAsync(HttpResponseMessage response, string schema)
    {
        var text = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        using var document = JsonDocument.Parse(text);
        var loaded = Schemas.GetOrAdd(schema, name => new Lazy<JsonSchema>(() => JsonSchema.FromFile(Path.Combine(AppContext.BaseDirectory, "schemas", name + ".json")))).Value;
        var result = loaded.Evaluate(document.RootElement, new EvaluationOptions { OutputFormat = OutputFormat.List });
        Assert.True(result.IsValid, $"{schema} invalide : {text}");
        return JsonNode.Parse(text)!;
    }

    public static async Task<JsonArray> AssertEachMatchesAsync(HttpResponseMessage response, string schema)
    {
        var text = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        using var document = JsonDocument.Parse(text);
        var loaded = Schemas.GetOrAdd(schema, name => new Lazy<JsonSchema>(() => JsonSchema.FromFile(Path.Combine(AppContext.BaseDirectory, "schemas", name + ".json")))).Value;
        foreach (var item in document.RootElement.EnumerateArray())
        {
            Assert.True(loaded.Evaluate(item).IsValid, $"{schema} invalide : {item}");
        }
        return JsonNode.Parse(text)!.AsArray();
    }
}
