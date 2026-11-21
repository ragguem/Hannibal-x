using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using Hannibal.Backoffice.Application;
using Hannibal.Backoffice.Application.Planning;

namespace Hannibal.Backoffice.Infrastructure.Planning;

/// <summary>Envoie la photo à <c>PUT /internal/missions/{id}/run</c> (contrat <c>RunMission</c>).</summary>
public sealed class HttpMissionLauncher(HttpClient client, Uri apiUrl, string? internalToken) : IMissionLauncher
{
    public const string InternalHeader = "X-Internal-Token";

    public async Task LaunchAsync(Guid missionId, MissionSnapshot snapshot, CancellationToken cancellationToken)
    {
        var body = new JsonObject
        {
            ["scenario_version"] = snapshot.ScenarioVersion,
            ["scenario"] = JsonNode.Parse(snapshot.ScenarioJson),
            ["player_ship"] = snapshot.PlayerShip,
            ["operator"] = snapshot.Operator,
            ["autopilot"] = snapshot.Autopilot,
            ["manual_helm"] = snapshot.ManualHelm,
            ["ships"] = new JsonArray([.. snapshot.Ships.Select(s => (JsonNode)new JsonObject
            {
                ["call_sign"] = s.CallSign,
                ["class_code"] = s.ClassCode,
                ["min_speed_knots"] = s.MinSpeedKnots,
                ["max_speed_knots"] = s.MaxSpeedKnots,
                ["turn_radius_meters"] = s.TurnRadiusMeters,
                ["length_meters"] = s.LengthMeters,
            })]),
        };
        using var request = new HttpRequestMessage(HttpMethod.Put, new Uri(apiUrl, $"/internal/missions/{missionId}/run"))
        {
            Content = JsonContent.Create(body),
        };
        if (internalToken is not null)
        {
            request.Headers.TryAddWithoutValidation(InternalHeader, internalToken);
        }
        HttpResponseMessage response;
        try
        {
            response = await client.SendAsync(request, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception e) when (e is HttpRequestException or TaskCanceledException && !cancellationToken.IsCancellationRequested)
        {
            throw new RuleViolation(RuleKind.Unavailable, $"apps/api injoignable : {e.Message}");
        }
        using (response)
        {
            if (response.IsSuccessStatusCode)
            {
                return;
            }
            var message = await MessageOfAsync(response, cancellationToken).ConfigureAwait(false);
            throw response.StatusCode switch
            {
                HttpStatusCode.Conflict => new RuleViolation(RuleKind.Conflict, "lancement refusé par apps/api", message),
                HttpStatusCode.NotFound or HttpStatusCode.UnprocessableEntity => new RuleViolation(RuleKind.Invalid, "photo refusée par apps/api", message),
                _ => new RuleViolation(RuleKind.Unavailable, $"apps/api a répondu {(int)response.StatusCode}"),
            };
        }
    }

    private static async Task<string?> MessageOfAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        try
        {
            var body = await response.Content.ReadFromJsonAsync<JsonObject>(cancellationToken).ConfigureAwait(false);
            return body?["message"]?.GetValue<string>();
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
