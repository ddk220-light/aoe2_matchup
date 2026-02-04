import json
import os

import pandas as pd
from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Get the unit output directory (same directory as app.py for Railway deployment)
UNIT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "unit_output")


def get_available_units():
    """Get list of available unit types from CSV files."""
    units = []
    for filename in os.listdir(UNIT_OUTPUT_DIR):
        if filename.endswith(".csv"):
            unit_name = filename.replace(".csv", "").replace("_", " ").title()
            units.append({"id": filename.replace(".csv", ""), "name": unit_name})
    return sorted(units, key=lambda x: x["name"])


def convert_to_native(obj):
    """Convert numpy/pandas types to native Python types for JSON serialization."""
    import numpy as np

    if isinstance(obj, dict):
        return {k: convert_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_native(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj


def get_unit_data(unit_id):
    """Load unit data from CSV and compute unique stats."""
    filepath = os.path.join(UNIT_OUTPUT_DIR, f"{unit_id}.csv")
    if not os.path.exists(filepath):
        return None

    df = pd.read_csv(filepath)

    # Filter to civs that have/don't have the unit
    df_has_unit = df[df["Has_Unit"] == "Yes"].copy()
    df_missing_unit = df[df["Has_Unit"] == "No"].copy()

    # Get list of civs missing this unit
    missing_civs = sorted(df_missing_unit["Civilization"].tolist())

    # Identify numeric columns for uniqueness detection
    numeric_cols = [
        "HP",
        "Attack",
        "Range",
        "Attack_Speed",
        "Melee_Armor",
        "Pierce_Armor",
        "Movement_Speed",
        "Cost_Food",
        "Cost_Wood",
        "Cost_Gold",
        "Creation_Time",
        "Upgrade_Cost",
    ]

    # Get columns that exist in this dataframe
    existing_numeric_cols = [col for col in numeric_cols if col in df.columns]

    # Find unique values for each stat
    unique_stats = {}
    for col in existing_numeric_cols:
        values = df_has_unit[col].dropna()
        if len(values) > 0:
            # Find the most common value (baseline)
            mode_val = values.mode()
            if len(mode_val) > 0:
                baseline = mode_val.iloc[0]
                # Mark values that differ from baseline as unique
                unique_stats[col] = {
                    "baseline": convert_to_native(baseline),
                    "unique_civs": {},
                }
                for idx, row in df_has_unit.iterrows():
                    val = row[col]
                    if pd.notna(val) and val != baseline:
                        civ = row["Civilization"]
                        unique_stats[col]["unique_civs"][civ] = convert_to_native(val)

    # Convert dataframe to records and ensure all values are JSON serializable
    records = df_has_unit.to_dict(orient="records")
    records = convert_to_native(records)
    columns = list(df.columns)

    # Remove Has_Unit from display
    if "Has_Unit" in columns:
        columns.remove("Has_Unit")

    return {
        "records": records,
        "columns": columns,
        "unique_stats": unique_stats,
        "total_civs": len(df_has_unit),
        "missing_civs": missing_civs,
    }


@app.route("/")
def index():
    units = get_available_units()
    return render_template("index.html", units=units)


@app.route("/api/units")
def api_units():
    return jsonify(get_available_units())


@app.route("/api/unit/<unit_id>")
def api_unit_data(unit_id):
    data = get_unit_data(unit_id)
    if data is None:
        return jsonify({"error": "Unit not found"}), 404
    return jsonify(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
