using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Hannibal.Backoffice.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class ScenarioSources : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<Guid>(
                name: "imported_by",
                schema: "catalog",
                table: "scenario_versions",
                type: "uuid",
                nullable: true,
                oldClrType: typeof(Guid),
                oldType: "uuid");

            migrationBuilder.AddColumn<string>(
                name: "source",
                schema: "catalog",
                table: "scenario_versions",
                type: "text",
                nullable: false,
                defaultValue: "");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "source",
                schema: "catalog",
                table: "scenario_versions");

            migrationBuilder.AlterColumn<Guid>(
                name: "imported_by",
                schema: "catalog",
                table: "scenario_versions",
                type: "uuid",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"),
                oldClrType: typeof(Guid),
                oldType: "uuid",
                oldNullable: true);
        }
    }
}
