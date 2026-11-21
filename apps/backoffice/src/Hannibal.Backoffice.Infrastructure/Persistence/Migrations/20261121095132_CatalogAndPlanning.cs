using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Hannibal.Backoffice.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class CatalogAndPlanning : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.EnsureSchema(
                name: "planning");

            migrationBuilder.EnsureSchema(
                name: "catalog");

            migrationBuilder.AddColumn<DateTimeOffset>(
                name: "password_changed_at",
                schema: "identity",
                table: "users",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "scenarios",
                schema: "catalog",
                columns: table => new
                {
                    id = table.Column<string>(type: "text", nullable: false),
                    title = table.Column<string>(type: "text", nullable: false),
                    level = table.Column<string>(type: "text", nullable: false),
                    published_version = table.Column<int>(type: "integer", nullable: true),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    archived_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_scenarios", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "ship_classes",
                schema: "catalog",
                columns: table => new
                {
                    code = table.Column<string>(type: "text", nullable: false),
                    label = table.Column<string>(type: "text", nullable: false),
                    min_speed_kn = table.Column<int>(type: "integer", nullable: false),
                    max_speed_kn = table.Column<int>(type: "integer", nullable: false),
                    turn_rate_deg_s = table.Column<double>(type: "double precision", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ship_classes", x => x.code);
                    table.CheckConstraint("ck_ship_classes_speed_bounds", "min_speed_kn > 0 AND min_speed_kn <= max_speed_kn");
                    table.CheckConstraint("ck_ship_classes_turn_rate", "turn_rate_deg_s > 0");
                });

            migrationBuilder.CreateTable(
                name: "scenario_versions",
                schema: "catalog",
                columns: table => new
                {
                    scenario_id = table.Column<string>(type: "text", nullable: false),
                    version = table.Column<int>(type: "integer", nullable: false),
                    document = table.Column<string>(type: "jsonb", nullable: false),
                    content_sha256 = table.Column<string>(type: "text", nullable: false),
                    imported_by = table.Column<Guid>(type: "uuid", nullable: false),
                    imported_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_scenario_versions", x => new { x.scenario_id, x.version });
                    table.ForeignKey(
                        name: "FK_scenario_versions_scenarios_scenario_id",
                        column: x => x.scenario_id,
                        principalSchema: "catalog",
                        principalTable: "scenarios",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_scenario_versions_users_imported_by",
                        column: x => x.imported_by,
                        principalSchema: "identity",
                        principalTable: "users",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "ships",
                schema: "catalog",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    call_sign = table.Column<string>(type: "text", nullable: false),
                    class_code = table.Column<string>(type: "text", nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    retired_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ships", x => x.id);
                    table.ForeignKey(
                        name: "FK_ships_ship_classes_class_code",
                        column: x => x.class_code,
                        principalSchema: "catalog",
                        principalTable: "ship_classes",
                        principalColumn: "code",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "missions",
                schema: "planning",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    scenario_id = table.Column<string>(type: "text", nullable: false),
                    scenario_version = table.Column<int>(type: "integer", nullable: false),
                    state = table.Column<string>(type: "text", nullable: false),
                    runner = table.Column<string>(type: "text", nullable: true),
                    planned_by = table.Column<Guid>(type: "uuid", nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    launched_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    archived_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_missions", x => x.id);
                    table.CheckConstraint("ck_missions_state", "state IN ('planned', 'launching', 'running', 'finished', 'stopped', 'archived')");
                    table.ForeignKey(
                        name: "FK_missions_scenario_versions_scenario_id_scenario_version",
                        columns: x => new { x.scenario_id, x.scenario_version },
                        principalSchema: "catalog",
                        principalTable: "scenario_versions",
                        principalColumns: new[] { "scenario_id", "version" },
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_missions_users_planned_by",
                        column: x => x.planned_by,
                        principalSchema: "identity",
                        principalTable: "users",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "mission_participants",
                schema: "planning",
                columns: table => new
                {
                    mission_id = table.Column<Guid>(type: "uuid", nullable: false),
                    ship_id = table.Column<Guid>(type: "uuid", nullable: false),
                    user_id = table.Column<Guid>(type: "uuid", nullable: false),
                    game_role_code = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_mission_participants", x => new { x.mission_id, x.ship_id });
                    table.ForeignKey(
                        name: "FK_mission_participants_game_roles_game_role_code",
                        column: x => x.game_role_code,
                        principalSchema: "identity",
                        principalTable: "game_roles",
                        principalColumn: "code",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_mission_participants_missions_mission_id",
                        column: x => x.mission_id,
                        principalSchema: "planning",
                        principalTable: "missions",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_mission_participants_ships_ship_id",
                        column: x => x.ship_id,
                        principalSchema: "catalog",
                        principalTable: "ships",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_mission_participants_users_user_id",
                        column: x => x.user_id,
                        principalSchema: "identity",
                        principalTable: "users",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateIndex(
                name: "IX_mission_participants_game_role_code",
                schema: "planning",
                table: "mission_participants",
                column: "game_role_code");

            migrationBuilder.CreateIndex(
                name: "IX_mission_participants_mission_id_user_id",
                schema: "planning",
                table: "mission_participants",
                columns: new[] { "mission_id", "user_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_mission_participants_ship_id",
                schema: "planning",
                table: "mission_participants",
                column: "ship_id");

            migrationBuilder.CreateIndex(
                name: "IX_mission_participants_user_id",
                schema: "planning",
                table: "mission_participants",
                column: "user_id");

            migrationBuilder.CreateIndex(
                name: "IX_missions_planned_by",
                schema: "planning",
                table: "missions",
                column: "planned_by");

            migrationBuilder.CreateIndex(
                name: "IX_missions_scenario_id_scenario_version",
                schema: "planning",
                table: "missions",
                columns: new[] { "scenario_id", "scenario_version" });

            migrationBuilder.CreateIndex(
                name: "IX_missions_state_created_at_id",
                schema: "planning",
                table: "missions",
                columns: new[] { "state", "created_at", "id" },
                descending: new[] { false, true, true });

            migrationBuilder.CreateIndex(
                name: "IX_scenario_versions_imported_by",
                schema: "catalog",
                table: "scenario_versions",
                column: "imported_by");

            migrationBuilder.CreateIndex(
                name: "IX_ships_call_sign",
                schema: "catalog",
                table: "ships",
                column: "call_sign",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_ships_class_code",
                schema: "catalog",
                table: "ships",
                column: "class_code");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "mission_participants",
                schema: "planning");

            migrationBuilder.DropTable(
                name: "missions",
                schema: "planning");

            migrationBuilder.DropTable(
                name: "ships",
                schema: "catalog");

            migrationBuilder.DropTable(
                name: "scenario_versions",
                schema: "catalog");

            migrationBuilder.DropTable(
                name: "ship_classes",
                schema: "catalog");

            migrationBuilder.DropTable(
                name: "scenarios",
                schema: "catalog");

            migrationBuilder.DropColumn(
                name: "password_changed_at",
                schema: "identity",
                table: "users");
        }
    }
}
