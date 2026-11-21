using System.Runtime.CompilerServices;
using System.Text.Json.Nodes;

namespace Hannibal.Backoffice.Tests;

/// <summary>
/// Le document OpenAPI publié est généré par le service ; la copie versionnée doit le suivre.
/// Pour la régénérer : <c>HX_UPDATE_OPENAPI=1 dotnet test</c>.
/// </summary>
public sealed class OpenApiDocumentTests
{
    [Fact]
    public async Task Published_document_matches_the_running_service()
    {
        await using var app = Backoffice.Create();
        using var client = app.CreateClient();

        var served = JsonNode.Parse(await client.GetStringAsync(new Uri("/openapi/v1.json", UriKind.Relative), TestContext.Current.CancellationToken))!;
        var path = PublishedDocumentPath();

        if (Environment.GetEnvironmentVariable("HX_UPDATE_OPENAPI") == "1")
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            await File.WriteAllTextAsync(path, served.ToJsonString(new() { WriteIndented = true }) + "\n", TestContext.Current.CancellationToken);
        }

        var published = JsonNode.Parse(await File.ReadAllTextAsync(path, TestContext.Current.CancellationToken))!;
        Assert.True(JsonNode.DeepEquals(published, served), $"{path} n'est plus à jour : relancer les tests avec HX_UPDATE_OPENAPI=1.");
    }

    private static string PublishedDocumentPath([CallerFilePath] string source = "") =>
        Path.GetFullPath(Path.Combine(Path.GetDirectoryName(source)!, "..", "..", "openapi", "backoffice.v1.json"));
}
