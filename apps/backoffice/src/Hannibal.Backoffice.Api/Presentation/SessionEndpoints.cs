using System.Security.Claims;
using Hannibal.Backoffice.Api.Socle;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;

namespace Hannibal.Backoffice.Api.Presentation;

public sealed record SignInBody(string Username, string Password);

public sealed record SessionViewBody(string Username, string Role, IReadOnlyList<string> Permissions, DateTimeOffset ExpiresAt);

/// <summary><c>POST</c>, <c>GET</c>, <c>DELETE /v1/session</c> : connexion, session courante, déconnexion.</summary>
public static class SessionEndpoints
{
    public static IEndpointRouteBuilder MapSession(this IEndpointRouteBuilder app)
    {
        var session = app.MapGroup("/v1/session").WithTags("session");

        session.MapPost("", async (SignInBody body, Sessions sessions, BackofficeSettings settings, HttpContext context, CancellationToken ct) =>
        {
            if (string.IsNullOrEmpty(body.Username) || string.IsNullOrEmpty(body.Password))
            {
                throw new UnauthenticatedException("identifiant ou mot de passe vide");
            }
            var signedIn = await sessions.SignInAsync(body.Username, body.Password, ct).ConfigureAwait(false)
                ?? throw new UnauthenticatedException("identifiant ou mot de passe refusé");
            context.Response.Cookies.Append(SessionAuthentication.CookieName, signedIn.Token, new CookieOptions
            {
                HttpOnly = true,
                Secure = !settings.IsLocal,
                SameSite = SameSiteMode.Strict,
                Path = "/",
                IsEssential = true,
            });
            return Results.Json(ToView(signedIn.User, signedIn.ExpiresAt), Json.Options);
        });

        session.MapGet("", (HttpContext context) =>
        {
            var user = context.User;
            var permissions = user.FindAll(SessionAuthentication.PermissionClaim).Select(c => c.Value).Order(StringComparer.Ordinal).ToList();
            var expiresAt = (DateTimeOffset)context.Items[SessionAuthentication.ExpiresAtItem]!;
            return Results.Json(new SessionViewBody(user.Identity!.Name!, user.FindFirstValue(ClaimTypes.Role)!, permissions, expiresAt), Json.Options);
        }).RequireAuthorization();

        session.MapDelete("", async (HttpContext context, Sessions sessions, CancellationToken ct) =>
        {
            if (context.Request.Cookies.TryGetValue(SessionAuthentication.CookieName, out var token))
            {
                await sessions.SignOutAsync(token, ct).ConfigureAwait(false);
            }
            context.Response.Cookies.Delete(SessionAuthentication.CookieName, new CookieOptions { Path = "/" });
            return Results.NoContent();
        });

        return app;
    }

    private static SessionViewBody ToView(AuthenticatedUser user, DateTimeOffset expiresAt) =>
        new(user.Username, user.RoleCode, [.. user.Permissions.Order(StringComparer.Ordinal)], expiresAt);
}
