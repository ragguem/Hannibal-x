using System.Security.Claims;
using Hannibal.Backoffice.Api.Socle;
using Hannibal.Backoffice.Application.Identity;
using Hannibal.Backoffice.Domain.Identity;

namespace Hannibal.Backoffice.Api.Presentation;

public sealed record UserViewBody(
    Guid Id,
    string Username,
    string Role,
    DateTimeOffset CreatedAt,
    DateTimeOffset? DisabledAt,
    DateTimeOffset? PasswordChangedAt);

public sealed record UserListBody(IReadOnlyList<UserViewBody> Users);

public sealed record RoleViewBody(string Code, string Label, IReadOnlyList<string> Permissions);

public sealed record RoleListBody(IReadOnlyList<RoleViewBody> Roles);

public sealed record CreateUserBody(string Username, string Role);

public sealed record ChangeUserRoleBody(string Role);

public sealed record IssuedPasswordBody(UserViewBody User, string TemporaryPassword);

public sealed record ChangePasswordBody(string CurrentPassword, string NewPassword);

/// <summary>Comptes et rôles (Lot 7.2), réservés à <c>user:manage</c> ; changement de son propre mot de passe.</summary>
public static class UserEndpoints
{
    public static IEndpointRouteBuilder MapUsers(this IEndpointRouteBuilder app)
    {
        var users = app.MapGroup("/v1/users").WithTags("utilisateurs").RequireAuthorization(Permission.UserManage);

        users.MapGet("", async (Users handler, CancellationToken ct) =>
            Results.Json(new UserListBody([.. (await handler.ListAsync(ct).ConfigureAwait(false)).Select(ToView)]), Json.Options))
            .Produces<UserListBody>();

        users.MapPost("", async (CreateUserBody body, Users handler, CancellationToken ct) =>
        {
            var issued = await handler.CreateAsync(body.Username ?? "", body.Role ?? "", ct).ConfigureAwait(false);
            return Results.Json(ToView(issued), Json.Options, statusCode: StatusCodes.Status201Created);
        }).Produces<IssuedPasswordBody>(StatusCodes.Status201Created);

        users.MapPut("/{id:guid}/role", async (Guid id, ChangeUserRoleBody body, Users handler, HttpContext context, CancellationToken ct) =>
            Results.Json(ToView(await handler.ChangeRoleAsync(ActorId(context), id, body.Role ?? "", ct).ConfigureAwait(false)), Json.Options))
            .Produces<UserViewBody>();

        users.MapPost("/{id:guid}/disable", async (Guid id, Users handler, HttpContext context, CancellationToken ct) =>
            Results.Json(ToView(await handler.DisableAsync(ActorId(context), id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<UserViewBody>();

        users.MapPost("/{id:guid}/enable", async (Guid id, Users handler, CancellationToken ct) =>
            Results.Json(ToView(await handler.EnableAsync(id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<UserViewBody>();

        users.MapPost("/{id:guid}/password-reset", async (Guid id, Users handler, CancellationToken ct) =>
            Results.Json(ToView(await handler.ResetPasswordAsync(id, ct).ConfigureAwait(false)), Json.Options))
            .Produces<IssuedPasswordBody>();

        app.MapGet("/v1/roles", () => Results.Json(
                new RoleListBody([.. IdentityCatalog.Roles.Select(r => new RoleViewBody(r.Code, r.Label, r.Permissions))]),
                Json.Options))
            .WithTags("utilisateurs")
            .Produces<RoleListBody>()
            .RequireAuthorization(Permission.UserManage);

        app.MapPut("/v1/session/password", async (ChangePasswordBody body, Users handler, HttpContext context, CancellationToken ct) =>
            {
                await handler.ChangeOwnPasswordAsync(ActorId(context), body.CurrentPassword ?? "", body.NewPassword ?? "", ct).ConfigureAwait(false);
                context.Response.Cookies.Delete(SessionAuthentication.CookieName, new CookieOptions { Path = "/" });
                return Results.NoContent();
            })
            .WithTags("session")
            .Produces(StatusCodes.Status204NoContent)
            .RequireAuthorization();

        return app;
    }

    private static Guid ActorId(HttpContext context) => Guid.Parse(context.User.FindFirstValue(ClaimTypes.NameIdentifier)!);

    private static UserViewBody ToView(UserSummary u) => new(u.Id, u.Username, u.RoleCode, u.CreatedAt, u.DisabledAt, u.PasswordChangedAt);

    private static IssuedPasswordBody ToView(IssuedPassword issued) => new(ToView(issued.User), issued.TemporaryPassword);
}
