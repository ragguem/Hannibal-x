using Hannibal.Backoffice.Infrastructure.Security;

namespace Hannibal.Backoffice.Tests;

public sealed class PasswordHasherTests
{
    private readonly Argon2idPasswordHasher _hasher = new(memoryKib: 1024, iterations: 1);

    [Fact]
    public void Une_empreinte_porte_ses_parametres_et_se_verifie()
    {
        var encoded = _hasher.Hash("mot-de-passe-de-test");

        Assert.StartsWith("$argon2id$v=19$m=1024,t=1,p=1$", encoded, StringComparison.Ordinal);
        Assert.True(_hasher.Verify("mot-de-passe-de-test", encoded));
        Assert.False(_hasher.Verify("autre-mot-de-passe", encoded));
    }

    [Fact]
    public void Deux_empreintes_du_meme_mot_de_passe_different_par_le_sel()
    {
        Assert.NotEqual(_hasher.Hash("identique"), _hasher.Hash("identique"));
    }

    [Fact]
    public void Une_empreinte_faite_avec_d_autres_parametres_reste_verifiable()
    {
        var older = new Argon2idPasswordHasher(memoryKib: 2048, iterations: 2).Hash("ancien");

        Assert.True(_hasher.Verify("ancien", older));
    }

    [Theory]
    [InlineData("")]
    [InlineData("$2b$10$autre-algorithme")]
    [InlineData("$argon2id$v=19$m=1024,t=1,p=1$incomplet")]
    public void Une_empreinte_inconnue_est_refusee(string encoded)
    {
        Assert.False(_hasher.Verify("x", encoded));
    }
}
