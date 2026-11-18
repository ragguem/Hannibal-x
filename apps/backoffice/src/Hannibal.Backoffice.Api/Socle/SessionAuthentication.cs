using System.Security.Claims;
using System.Text.Encodings.Web;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Options;

namespace Hannibal.Backoffice.Api.Socle;

/// <summary>Authentification par le cookie de session ; une politique d'autorisation par permission.</summary>
public sealed class SessionAuthentication(
    IOptionsMonitor<AuthenticationSchemeOptions> options,
    ILoggerFactory logger,
    UrlEncoder encoder,
    Sessions sessions) : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    public const string SchemeName = "hx-session";
    public const string CookieName = "hx_session";
    public const string PermissionClaim = "hx:permission";
    public const string ExpiresAtItem = "hx.session_expires_at";

    protected override async Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Cookies.TryGetValue(CookieName, out var token) || token.Length == 0)
        {
            return AuthenticateResult.NoResult();
        }
        var session = await sessions.AuthenticateAsync(token, Context.RequestAborted).ConfigureAwait(false);
        if (session is null)
        {
            return AuthenticateResult.Fail("session inconnue, expirée ou révoquée");
        }
        Context.Items[ExpiresAtItem] = session.ExpiresAt;
        return AuthenticateResult.Success(new AuthenticationTicket(ToPrincipal(session.User), SchemeName));
    }

    protected override Task HandleChallengeAsync(AuthenticationProperties properties) =>
        throw new UnauthenticatedException("session absente ou invalide");

    protected override Task HandleForbiddenAsync(AuthenticationProperties properties) =>
        throw new ForbiddenException("permission manquante");

    public static ClaimsPrincipal ToPrincipal(AuthenticatedUser user)
    {
        var claims = new List<Claim>
        {
            new(ClaimTypes.NameIdentifier, user.Id.ToString()),
            new(ClaimTypes.Name, user.Username),
            new(ClaimTypes.Role, user.RoleCode),
        };
        claims.AddRange(user.Permissions.Select(p => new Claim(PermissionClaim, p)));
        return new ClaimsPrincipal(new ClaimsIdentity(claims, SchemeName));
    }
}

public static class SessionAuthenticationSetup
{
    public static IServiceCollection AddSessionAuthentication(this IServiceCollection services)
    {
        services.AddAuthentication(SessionAuthentication.SchemeName)
            .AddScheme<AuthenticationSchemeOptions, SessionAuthentication>(SessionAuthentication.SchemeName, null);
        services.AddAuthorizationBuilder().AddPermissionPolicies();
        return services;
    }

    private static AuthorizationBuilder AddPermissionPolicies(this AuthorizationBuilder builder)
    {
        foreach (var permission in IdentityCatalog.Roles.SelectMany(r => r.Permissions).Distinct(StringComparer.Ordinal))
        {
            builder.AddPolicy(permission, policy => policy.RequireAuthenticatedUser().RequireClaim(SessionAuthentication.PermissionClaim, permission));
        }
        return builder;
    }
}
