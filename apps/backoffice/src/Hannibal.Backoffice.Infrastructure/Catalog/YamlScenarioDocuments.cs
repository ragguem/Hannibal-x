using System.Globalization;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Hannibal.Backoffice.Application;
using Hannibal.Backoffice.Application.Catalog;
using Json.Schema;
using YamlDotNet.Core;
using YamlDotNet.Serialization;

namespace Hannibal.Backoffice.Infrastructure.Catalog;

/// <summary>YAML vers JSON, puis le JSON Schema <c>ScenarioDocument</c> embarqué (même source que le contrat Python).</summary>
public sealed class YamlScenarioDocuments : IScenarioDocuments
{
    public const int MaxSourceLength = 256 * 1024;

    private static readonly Lazy<JsonSchema> Schema = new(() => JsonSchema.FromText(ReadResource("ScenarioDocument.json")));

    private static readonly IDeserializer Yaml = new DeserializerBuilder().WithAttemptingUnquotedStringTypeDeserialization().Build();

    /// <summary>Les scénarios du dépôt, semés au premier démarrage.</summary>
    public static IEnumerable<string> RepositoryScenarios() =>
        typeof(YamlScenarioDocuments).Assembly.GetManifestResourceNames()
            .Where(name => name.StartsWith("scenarios/", StringComparison.Ordinal))
            .Order(StringComparer.Ordinal)
            .Select(ReadResource);

    public ParsedScenario Parse(string yaml)
    {
        if (yaml.Length is 0 or > MaxSourceLength)
        {
            throw Refused("Fichier vide ou trop volumineux (256 Ko au plus).");
        }
        JsonNode? node;
        try
        {
            node = ToJson(Yaml.Deserialize<object?>(yaml));
        }
        catch (YamlException e)
        {
            throw Refused($"YAML illisible, ligne {e.Start.Line} : {e.Message}");
        }
        if (node is not JsonObject document)
        {
            throw Refused("Le fichier doit décrire un scénario (un objet YAML).");
        }
        var json = document.ToJsonString();
        using var parsed = JsonDocument.Parse(json);
        var result = Schema.Value.Evaluate(parsed.RootElement, new EvaluationOptions { OutputFormat = OutputFormat.List });
        if (!result.IsValid)
        {
            var first = result.Details?.FirstOrDefault(d => d.Errors is { Count: > 0 });
            var where = first?.InstanceLocation.ToString() is { Length: > 0 } location ? location : "/";
            var why = first?.Errors?.Values.FirstOrDefault() ?? "document non conforme";
            throw Refused($"Scénario non conforme en {where} : {why}");
        }
        var fleet = document["flotte"]!.AsArray().Select(member => (string)member!["nom"]!).ToList();
        return new ParsedScenario((string)document["id"]!, (string)document["titre"]!, (string)document["niveau"]!, fleet, json, Sha256(yaml));
    }

    private static RuleViolation Refused(string message) => new(RuleKind.Invalid, "scénario refusé", message);

    private static string Sha256(string yaml) =>
        Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(yaml.ReplaceLineEndings("\n"))));

    private static JsonNode? ToJson(object? value) => value switch
    {
        null => null,
        IDictionary<object, object?> map => new JsonObject(map.Select(p =>
            KeyValuePair.Create(Convert.ToString(p.Key, CultureInfo.InvariantCulture)!, ToJson(p.Value)))),
        IList<object?> list => new JsonArray([.. list.Select(ToJson)]),
        string s => JsonValue.Create(s),
        bool b => JsonValue.Create(b),
        int or long or short or byte => JsonValue.Create(Convert.ToInt64(value, CultureInfo.InvariantCulture)),
        IConvertible number => JsonValue.Create(Convert.ToDouble(number, CultureInfo.InvariantCulture)),
        _ => JsonValue.Create(Convert.ToString(value, CultureInfo.InvariantCulture)),
    };

    private static string ReadResource(string name)
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name)
            ?? throw new InvalidOperationException($"ressource embarquée absente : {name}");
        using var reader = new StreamReader(stream, Encoding.UTF8);
        return reader.ReadToEnd();
    }
}
