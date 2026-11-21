using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Hannibal.Backoffice.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class ShipCharacteristics : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "ck_ship_classes_turn_rate",
                schema: "catalog",
                table: "ship_classes");

            migrationBuilder.RenameColumn(
                name: "turn_rate_deg_s",
                schema: "catalog",
                table: "ship_classes",
                newName: "turn_radius_m");

            migrationBuilder.AddColumn<double>(
                name: "length_m",
                schema: "catalog",
                table: "ship_classes",
                type: "double precision",
                nullable: false,
                defaultValue: 0.0);

            migrationBuilder.AddCheckConstraint(
                name: "ck_ship_classes_length",
                schema: "catalog",
                table: "ship_classes",
                sql: "length_m > 0");

            migrationBuilder.AddCheckConstraint(
                name: "ck_ship_classes_turn_radius",
                schema: "catalog",
                table: "ship_classes",
                sql: "turn_radius_m > 0");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "ck_ship_classes_length",
                schema: "catalog",
                table: "ship_classes");

            migrationBuilder.DropCheckConstraint(
                name: "ck_ship_classes_turn_radius",
                schema: "catalog",
                table: "ship_classes");

            migrationBuilder.DropColumn(
                name: "length_m",
                schema: "catalog",
                table: "ship_classes");

            migrationBuilder.RenameColumn(
                name: "turn_radius_m",
                schema: "catalog",
                table: "ship_classes",
                newName: "turn_rate_deg_s");

            migrationBuilder.AddCheckConstraint(
                name: "ck_ship_classes_turn_rate",
                schema: "catalog",
                table: "ship_classes",
                sql: "turn_rate_deg_s > 0");
        }
    }
}
