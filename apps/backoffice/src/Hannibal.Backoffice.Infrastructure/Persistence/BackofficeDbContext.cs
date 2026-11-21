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
    public DateTimeOffset? PasswordChangedAt { get; set; }
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

/// <summary>
/// Schémas <c>identity</c>, <c>catalog</c> et <c>planning</c>, dont le back-office est le seul écrivain (ADR 0007, Lot 7).
/// Noms de tables et de colonnes en snake_case.
/// </summary>
public sealed class BackofficeDbContext(DbContextOptions<BackofficeDbContext> options) : DbContext(options)
{
    public const string Schema = "identity";
    public const string CatalogSchema = "catalog";
    public const string PlanningSchema = "planning";
    public const string MigrationsHistoryTable = "__ef_migrations_history";
    public static readonly string[] MissionStates = ["planned", "launching", "running", "finished", "stopped", "archived"];

    public DbSet<RoleRow> Roles => Set<RoleRow>();
    public DbSet<RolePermissionRow> RolePermissions => Set<RolePermissionRow>();
    public DbSet<GameRoleRow> GameRoles => Set<GameRoleRow>();
    public DbSet<UserAccountRow> Users => Set<UserAccountRow>();
    public DbSet<SessionRow> Sessions => Set<SessionRow>();
    public DbSet<ShipClassRow> ShipClasses => Set<ShipClassRow>();
    public DbSet<ShipRow> Ships => Set<ShipRow>();
    public DbSet<ScenarioRow> Scenarios => Set<ScenarioRow>();
    public DbSet<ScenarioVersionRow> ScenarioVersions => Set<ScenarioVersionRow>();
    public DbSet<MissionRow> Missions => Set<MissionRow>();
    public DbSet<MissionParticipantRow> MissionParticipants => Set<MissionParticipantRow>();

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
            user.Property(u => u.PasswordChangedAt).HasColumnName("password_changed_at");
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

        ConfigureCatalog(modelBuilder);
        ConfigurePlanning(modelBuilder);
    }

    private static void ConfigureCatalog(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<ShipClassRow>(shipClass =>
        {
            shipClass.ToTable("ship_classes", CatalogSchema, table =>
            {
                table.HasCheckConstraint("ck_ship_classes_speed_bounds", "min_speed_kn > 0 AND min_speed_kn <= max_speed_kn");
                table.HasCheckConstraint("ck_ship_classes_turn_radius", "turn_radius_m > 0");
                table.HasCheckConstraint("ck_ship_classes_length", "length_m > 0");
            });
            shipClass.HasKey(c => c.Code);
            shipClass.Property(c => c.Code).HasColumnName("code");
            shipClass.Property(c => c.Label).HasColumnName("label");
            shipClass.Property(c => c.MinSpeedKnots).HasColumnName("min_speed_kn");
            shipClass.Property(c => c.MaxSpeedKnots).HasColumnName("max_speed_kn");
            shipClass.Property(c => c.TurnRadiusMeters).HasColumnName("turn_radius_m");
            shipClass.Property(c => c.LengthMeters).HasColumnName("length_m");
        });

        modelBuilder.Entity<ShipRow>(ship =>
        {
            ship.ToTable("ships", CatalogSchema);
            ship.HasKey(s => s.Id);
            ship.HasIndex(s => s.CallSign).IsUnique();
            ship.Property(s => s.Id).HasColumnName("id");
            ship.Property(s => s.CallSign).HasColumnName("call_sign");
            ship.Property(s => s.ClassCode).HasColumnName("class_code");
            ship.Property(s => s.CreatedAt).HasColumnName("created_at").HasDefaultValueSql("now()");
            ship.Property(s => s.RetiredAt).HasColumnName("retired_at");
            ship.HasOne<ShipClassRow>().WithMany().HasForeignKey(s => s.ClassCode).OnDelete(DeleteBehavior.Restrict);
        });

        modelBuilder.Entity<ScenarioRow>(scenario =>
        {
            scenario.ToTable("scenarios", CatalogSchema);
            scenario.HasKey(s => s.Id);
            scenario.Property(s => s.Id).HasColumnName("id");
            scenario.Property(s => s.Title).HasColumnName("title");
            scenario.Property(s => s.Level).HasColumnName("level");
            scenario.Property(s => s.PublishedVersion).HasColumnName("published_version");
            scenario.Property(s => s.CreatedAt).HasColumnName("created_at").HasDefaultValueSql("now()");
            scenario.Property(s => s.ArchivedAt).HasColumnName("archived_at");
        });

        modelBuilder.Entity<ScenarioVersionRow>(version =>
        {
            version.ToTable("scenario_versions", CatalogSchema);
            version.HasKey(v => new { v.ScenarioId, v.Version });
            version.Property(v => v.ScenarioId).HasColumnName("scenario_id");
            version.Property(v => v.Version).HasColumnName("version");
            version.Property(v => v.Document).HasColumnName("document").HasColumnType("jsonb");
            version.Property(v => v.ContentSha256).HasColumnName("content_sha256");
            version.Property(v => v.Source).HasColumnName("source");
            version.Property(v => v.ImportedBy).HasColumnName("imported_by");
            version.Property(v => v.ImportedAt).HasColumnName("imported_at").HasDefaultValueSql("now()");
            version.HasOne<ScenarioRow>().WithMany().HasForeignKey(v => v.ScenarioId).OnDelete(DeleteBehavior.Restrict);
            version.HasOne<UserAccountRow>().WithMany().HasForeignKey(v => v.ImportedBy).OnDelete(DeleteBehavior.Restrict);
        });
    }

    private static void ConfigurePlanning(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<MissionRow>(mission =>
        {
            var states = string.Join(", ", MissionStates.Select(s => $"'{s}'"));
            mission.ToTable("missions", PlanningSchema, table =>
                table.HasCheckConstraint("ck_missions_state", $"state IN ({states})"));
            mission.HasKey(m => m.Id);
            mission.HasIndex(m => new { m.State, m.CreatedAt, m.Id }).IsDescending(false, true, true);
            mission.Property(m => m.Id).HasColumnName("id").ValueGeneratedNever();
            mission.Property(m => m.ScenarioId).HasColumnName("scenario_id");
            mission.Property(m => m.ScenarioVersion).HasColumnName("scenario_version");
            mission.Property(m => m.State).HasColumnName("state");
            mission.Property(m => m.Runner).HasColumnName("runner");
            mission.Property(m => m.PlannedBy).HasColumnName("planned_by");
            mission.Property(m => m.CreatedAt).HasColumnName("created_at").HasDefaultValueSql("now()");
            mission.Property(m => m.LaunchedAt).HasColumnName("launched_at");
            mission.Property(m => m.ArchivedAt).HasColumnName("archived_at");
            mission.HasOne<ScenarioVersionRow>().WithMany()
                .HasForeignKey(m => new { m.ScenarioId, m.ScenarioVersion }).OnDelete(DeleteBehavior.Restrict);
            mission.HasOne<UserAccountRow>().WithMany().HasForeignKey(m => m.PlannedBy).OnDelete(DeleteBehavior.Restrict);
            mission.HasMany(m => m.Participants).WithOne().HasForeignKey(p => p.MissionId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<MissionParticipantRow>(participant =>
        {
            participant.ToTable("mission_participants", PlanningSchema);
            participant.HasKey(p => new { p.MissionId, p.ShipId });
            participant.HasIndex(p => new { p.MissionId, p.UserId }).IsUnique();
            participant.HasIndex(p => p.UserId);
            participant.Property(p => p.MissionId).HasColumnName("mission_id");
            participant.Property(p => p.ShipId).HasColumnName("ship_id");
            participant.Property(p => p.UserId).HasColumnName("user_id");
            participant.Property(p => p.GameRoleCode).HasColumnName("game_role_code");
            participant.HasOne<ShipRow>().WithMany().HasForeignKey(p => p.ShipId).OnDelete(DeleteBehavior.Restrict);
            participant.HasOne<UserAccountRow>().WithMany().HasForeignKey(p => p.UserId).OnDelete(DeleteBehavior.Restrict);
            participant.HasOne<GameRoleRow>().WithMany().HasForeignKey(p => p.GameRoleCode).OnDelete(DeleteBehavior.Restrict);
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
