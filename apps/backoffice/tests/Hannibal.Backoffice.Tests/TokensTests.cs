using Hannibal.Backoffice.Api.Socle;
using Microsoft.AspNetCore.Http;

namespace Hannibal.Backoffice.Tests;

public sealed class TokensTests
{
    private static HttpContext With(string? token)
    {
        var context = new DefaultHttpContext();
        if (token is not null)
        {
            context.Request.Headers[Tokens.InternalHeader] = token;
        }
        return context;
    }

    [Fact]
    public void Jeton_interne_correct_accepte() =>
        Tokens.RequireInternal(With("s3cret"), new BackofficeSettings { InternalToken = "s3cret", Environment = HxEnvironment.Production });

    [Fact]
    public void Jeton_interne_absent_ou_faux_refuse()
    {
        var settings = new BackofficeSettings { InternalToken = "s3cret" };
        Assert.Throws<UnauthenticatedException>(() => Tokens.RequireInternal(With(null), settings));
        Assert.Throws<ForbiddenException>(() => Tokens.RequireInternal(With("autre"), settings));
    }

    [Fact]
    public void Sans_jeton_configure_seul_le_local_passe()
    {
        Tokens.RequireInternal(With(null), new BackofficeSettings { Environment = HxEnvironment.Dev });
        Assert.Throws<ForbiddenException>(() =>
            Tokens.RequireInternal(With(null), new BackofficeSettings { Environment = HxEnvironment.Integration }));
    }
}
