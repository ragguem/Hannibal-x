using Hannibal.Backoffice.Application.Readiness;
using Hannibal.Backoffice.Domain;
using Hannibal.Backoffice.Infrastructure.Probes;
using NetArchTest.Rules;

namespace Hannibal.Backoffice.Tests;

/// <summary>Règles de couches, équivalent des contrats import-linter de `apps/api`.</summary>
public sealed class ArchitectureTests
{
    private const string Ns = "Hannibal.Backoffice";

    [Fact]
    public void Le_domaine_ne_depend_de_rien()
    {
        var result = Types.InAssembly(typeof(ReadinessReport).Assembly)
            .ShouldNot().HaveDependencyOnAny($"{Ns}.Application", $"{Ns}.Infrastructure", $"{Ns}.Api", "Microsoft.AspNetCore", "Microsoft.EntityFrameworkCore", "Npgsql", "System.Net.Http")
            .GetResult();
        Assert.True(result.IsSuccessful, string.Join(", ", result.FailingTypeNames ?? []));
    }

    [Fact]
    public void L_application_ne_connait_ni_le_web_ni_la_base()
    {
        var result = Types.InAssembly(typeof(CheckReadiness).Assembly)
            .ShouldNot().HaveDependencyOnAny($"{Ns}.Infrastructure", $"{Ns}.Api", "Microsoft.AspNetCore", "Microsoft.EntityFrameworkCore", "Npgsql", "System.Net.Http")
            .GetResult();
        Assert.True(result.IsSuccessful, string.Join(", ", result.FailingTypeNames ?? []));
    }

    [Fact]
    public void L_infrastructure_ne_connait_pas_le_web()
    {
        var result = Types.InAssembly(typeof(PostgresProbe).Assembly)
            .ShouldNot().HaveDependencyOnAny($"{Ns}.Api", "Microsoft.AspNetCore")
            .GetResult();
        Assert.True(result.IsSuccessful, string.Join(", ", result.FailingTypeNames ?? []));
    }
}
