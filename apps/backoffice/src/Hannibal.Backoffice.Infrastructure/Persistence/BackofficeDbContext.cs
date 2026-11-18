using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace Hannibal.Backoffice.Infrastructure.Persistence;

public sealed class RoleRow
{
    public required string Code { get; set; }
    public required string Label { get; set; }
    public List<RolePermissionRow> Permissions { get; set; } = [];
}

public sealed class RolePermissionRow
{
    public required string RoleCode { get; set; }
    public required string Permission { get; set; }
}

public sealed class GameRoleRow
{
    public required string Code { get; set; }
    public required string Label { get; set; }
    public required string Description { get; set; }
}

public sealed class UserAccountRow
{
    public Guid Id { get; set; }
    public required string Username { get; set; }
    public required string PasswordHash { get; set; }
    public required string RoleCode { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset? DisabledAt { get; set; }
}

public sealed class SessionRow
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public required byte[] TokenHash { get; set; }
    public DateTimeOffset ExpiresAt { get; set; }
    public DateTimeOffset AbsoluteExpiresAt { get; set; }
    public DateTimeOffset? RevokedAt { get; set; }
}

/// <summary>Schéma <c>identity</c> du back-office (ADR 0007). Noms de tables et de colonnes en snake_case.</summary>
public sealed class BackofficeDbContext(DbContextOptions<BackofficeDbContext> options) : DbContext(options)
{
    public const string Schema = "identity";
    public const string MigrationsHistoryTable = "__ef_migrations_history";

    public DbSet<RoleRow> Roles => Set<RoleRow>();
    public DbSet<RolePermissionRow> RolePermissions => Set<RolePermissionRow>();
    public DbSet<GameRoleRow> GameRoles => Set<GameRoleRow>();
    public DbSet<UserAccountRow> Users => Set<UserAccountRow>();
    public DbSet<SessionRow> Sessions => Set<SessionRow>();

    public static void Configure(DbContextOptionsBuilder builder, string connectionString) =>
        builder.UseNpgsql(connectionString, npgsql => npgsql.MigrationsHistoryTable(MigrationsHistoryTable, Schema));

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema(Schema);

        modelBuilder.Entity<RoleRow>(role =>
        {
            role.ToTable("roles");
            role.HasKey(r => r.Code);
            role.Property(r => r.Code).HasColumnName("code");
            role.Property(r => r.Label).HasColumnName("label");
            role.HasMany(r => r.Permissions).WithOne().HasForeignKey(p => p.RoleCode);
        });

        modelBuilder.Entity<RolePermissionRow>(permission =>
        {
            permission.ToTable("role_permissions");
            permission.HasKey(p => new { p.RoleCode, p.Permission });
            permission.Property(p => p.RoleCode).HasColumnName("role_code");
            permission.Property(p => p.Permission).HasColumnName("permission");
        });

        modelBuilder.Entity<GameRoleRow>(gameRole =>
        {
            gameRole.ToTable("game_roles");
            gameRole.HasKey(g => g.Code);
            gameRole.Property(g => g.Code).HasColumnName("code");
            gameRole.Property(g => g.Label).HasColumnName("label");
            gameRole.Property(g => g.Description).HasColumnName("description");
        });

        modelBuilder.Entity<UserAccountRow>(user =>
        {
            user.ToTable("users");
            user.HasKey(u => u.Id);
            user.HasIndex(u => u.Username).IsUnique();
            user.Property(u => u.Id).HasColumnName("id");
            user.Property(u => u.Username).HasColumnName("username");
            user.Property(u => u.PasswordHash).HasColumnName("password_hash");
            user.Property(u => u.RoleCode).HasColumnName("role_code");
            user.Property(u => u.CreatedAt).HasColumnName("created_at").HasDefaultValueSql("now()");
            user.Property(u => u.DisabledAt).HasColumnName("disabled_at");
            user.HasOne<RoleRow>().WithMany().HasForeignKey(u => u.RoleCode).OnDelete(DeleteBehavior.Restrict);
        });

        modelBuilder.Entity<SessionRow>(session =>
        {
            session.ToTable("sessions");
            session.HasKey(s => s.Id);
            session.HasIndex(s => s.TokenHash).IsUnique();
            session.Property(s => s.Id).HasColumnName("id");
            session.Property(s => s.UserId).HasColumnName("user_id");
            session.Property(s => s.TokenHash).HasColumnName("token_hash");
            session.Property(s => s.ExpiresAt).HasColumnName("expires_at");
            session.Property(s => s.AbsoluteExpiresAt).HasColumnName("absolute_expires_at");
            session.Property(s => s.RevokedAt).HasColumnName("revoked_at");
            session.HasOne<UserAccountRow>().WithMany().HasForeignKey(s => s.UserId).OnDelete(DeleteBehavior.Cascade);
        });
    }
}

/// <summary>Pour <c>dotnet ef migrations add</c> : aucune connexion n'est ouverte.</summary>
public sealed class BackofficeDbContextDesignFactory : IDesignTimeDbContextFactory<BackofficeDbContext>
{
    public BackofficeDbContext CreateDbContext(string[] args)
    {
        var builder = new DbContextOptionsBuilder<BackofficeDbContext>();
        BackofficeDbContext.Configure(builder, "Host=localhost;Database=hannibal_design");
        return new BackofficeDbContext(builder.Options);
    }
}
