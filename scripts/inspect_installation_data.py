
from pathlib import Path
import duckdb

ROOT = (
    Path("../Installation_Cost_Research_Database_CADENCE")
    .resolve()
)

files = {
    "Material prices - ZIP":
        ROOT / "roofing-cost-model/data_output/home_depot/2026-07-31/home_depot_material_price_by_zip.csv",
    "Material prices - CBSA":
        ROOT / "roofing-cost-model/data_output/home_depot/2026-07-31/home_depot_material_price_by_cbsa.csv",
    "Material prices - State":
        ROOT / "roofing-cost-model/data_output/home_depot/2026-07-31/home_depot_material_price_by_state.csv",
    "Material prices - National":
        ROOT / "roofing-cost-model/data_output/home_depot/2026-07-31/home_depot_material_price_national.csv",
    "Labor wages":
        ROOT / "data_output/labor/labor_wages_wide.parquet",
    "Labor projections":
        ROOT / "data_output/labor/labor_wage_projections_2026_2050.parquet",
    "Material escalation":
        ROOT / "roofing-cost-model/data_output/material_escalation_factors.parquet",
}

con = duckdb.connect()

for name, path in files.items():
    print(f"\n{'=' * 65}")
    print(name)
    print(f"File: {path}")

    if not path.exists():
        print("FILE NOT FOUND")
        continue

    source = (
        "read_parquet(?)"
        if path.suffix == ".parquet"
        else "read_csv_auto(?, all_varchar=true)"
    )

    print("\nSCHEMA:")
    schema = con.execute(
        f"DESCRIBE SELECT * FROM {source}",
        [str(path)],
    ).fetchall()

    for column in schema:
        print(f"  {column[0]}: {column[1]}")

    print("\nFIRST 3 ROWS:")

result = con.execute(
    f"SELECT * FROM {source} LIMIT 3",
    [str(path)],
)

column_names = [col[0] for col in result.description]
rows = result.fetchall()

for row in rows:
    print(dict(zip(column_names, row)))

con.close()
