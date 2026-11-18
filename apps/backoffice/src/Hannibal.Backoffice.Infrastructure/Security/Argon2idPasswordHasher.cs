using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Hannibal.Backoffice.Application.Identity;
using Konscious.Security.Cryptography;

namespace Hannibal.Backoffice.Infrastructure.Security;

/// <summary>
/// Argon2id au format PHC : <c>$argon2id$v=19$m=19456,t=2,p=1$sel$empreinte</c> (base64 sans remplissage).
/// Les paramètres sont lus dans l'empreinte : un durcissement ultérieur ne rend pas les anciennes empreintes invalides.
/// </summary>
public sealed class Argon2idPasswordHasher(int memoryKib = 19456, int iterations = 2, int parallelism = 1) : IPasswordHasher
{
    private const string Prefix = "$argon2id$v=19$";
    private const int SaltBytes = 16;
    private const int HashBytes = 32;

    public string Hash(string password)
    {
        var salt = RandomNumberGenerator.GetBytes(SaltBytes);
        var hash = Compute(password, salt, memoryKib, iterations, parallelism, HashBytes);
        return string.Create(
            CultureInfo.InvariantCulture,
            $"{Prefix}m={memoryKib},t={iterations},p={parallelism}${Encode(salt)}${Encode(hash)}");
    }

    public bool Verify(string password, string encodedHash)
    {
        if (!encodedHash.StartsWith(Prefix, StringComparison.Ordinal))
        {
            return false;
        }
        var parts = encodedHash[Prefix.Length..].Split('$');
        if (parts.Length != 3)
        {
            return false;
        }
        var parameters = parts[0].Split(',').Select(p => p.Split('=')).ToDictionary(p => p[0], p => int.Parse(p[1], CultureInfo.InvariantCulture));
        var expected = Decode(parts[2]);
        var actual = Compute(password, Decode(parts[1]), parameters["m"], parameters["t"], parameters["p"], expected.Length);
        return CryptographicOperations.FixedTimeEquals(actual, expected);
    }

    private static byte[] Compute(string password, byte[] salt, int memory, int passes, int lanes, int length)
    {
        using var argon2 = new Argon2id(Encoding.UTF8.GetBytes(password))
        {
            Salt = salt,
            MemorySize = memory,
            Iterations = passes,
            DegreeOfParallelism = lanes,
        };
        return argon2.GetBytes(length);
    }

    private static string Encode(byte[] bytes) => Convert.ToBase64String(bytes).TrimEnd('=');

    private static byte[] Decode(string text) => Convert.FromBase64String(text.PadRight(text.Length + ((4 - (text.Length % 4)) % 4), '='));
}
