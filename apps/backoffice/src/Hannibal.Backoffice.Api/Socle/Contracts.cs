using System.Text.Json;
using System.Text.Json.Serialization;

namespace Hannibal.Backoffice.Api.Socle;

/// <summary>Miroirs des schémas de `packages/contracts/schemas`, vérifiés par `ContractTests`.</summary>
public sealed record ErrorBody(string Code, string Message, string? RequestId, string? Dependency = null);

public sealed record Health(string Status, string Service, string Version);

public sealed record DependencyStatusBody(string Name, string State, double? LatencyMs);

public sealed record ReadinessBody(string Status, string Service, string Version, IReadOnlyList<DependencyStatusBody> Dependencies);

public static class Json
{
    public static readonly JsonSerializerOptions Options = Configure(new JsonSerializerOptions(JsonSerializerDefaults.Web));

    public static JsonSerializerOptions Configure(JsonSerializerOptions options)
    {
        options.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
        options.DefaultIgnoreCondition = JsonIgnoreCondition.Never;
        return options;
    }
}
