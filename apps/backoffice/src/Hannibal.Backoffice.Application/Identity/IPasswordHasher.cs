namespace Hannibal.Backoffice.Application.Identity;

/// <summary>Hachage des mots de passe. Le résultat porte son algorithme et ses paramètres (format PHC).</summary>
public interface IPasswordHasher
{
    string Hash(string password);

    bool Verify(string password, string encodedHash);
}
