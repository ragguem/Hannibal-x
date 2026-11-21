using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Hannibal.Backoffice.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class MissionPlanning : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "ck_missions_state",
                schema: "planning",
                table: "missions");

            migrationBuilder.AddColumn<bool>(
                name: "autopilot",
                schema: "planning",
                table: "missions",
                type: "boolean",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<bool>(
                name: "manual_helm",
                schema: "planning",
                table: "missions",
                type: "boolean",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<Guid>(
                name: "player_ship_id",
                schema: "planning",
                table: "missions",
                type: "uuid",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            migrationBuilder.CreateIndex(
                name: "IX_missions_player_ship_id",
                schema: "planning",
                table: "missions",
                column: "player_ship_id");

            migrationBuilder.AddCheckConstraint(
                name: "ck_missions_state",
                schema: "planning",
                table: "missions",
                sql: "state IN ('planned', 'ready', 'launching', 'running', 'finished', 'stopped', 'archived')");

            migrationBuilder.AddForeignKey(
                name: "FK_missions_ships_player_ship_id",
                schema: "planning",
                table: "missions",
                column: "player_ship_id",
                principalSchema: "catalog",
                principalTable: "ships",
                principalColumn: "id",
                onDelete: ReferentialAction.Restrict);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_missions_ships_player_ship_id",
                schema: "planning",
                table: "missions");

            migrationBuilder.DropIndex(
                name: "IX_missions_player_ship_id",
                schema: "planning",
                table: "missions");

            migrationBuilder.DropCheckConstraint(
                name: "ck_missions_state",
                schema: "planning",
                table: "missions");

            migrationBuilder.DropColumn(
                name: "autopilot",
                schema: "planning",
                table: "missions");

            migrationBuilder.DropColumn(
                name: "manual_helm",
                schema: "planning",
                table: "missions");

            migrationBuilder.DropColumn(
                name: "player_ship_id",
                schema: "planning",
                table: "missions");

            migrationBuilder.AddCheckConstraint(
                name: "ck_missions_state",
                schema: "planning",
                table: "missions",
                sql: "state IN ('planned', 'launching', 'running', 'finished', 'stopped', 'archived')");
        }
    }
}
