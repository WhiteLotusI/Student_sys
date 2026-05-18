"""
Run the full Student Data Review System pipeline.

From project root:
    python scripts/run_all.py

This version supports multiple CSV files placed inside the uploads/ folder.
"""

from pathlib import Path
import sys
import pandas as pd


# =========================================
# PROJECT ROOT + IMPORT PATH
# =========================================

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

UPLOAD_FOLDER = ROOT / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


# =========================================
# IMPORT PIPELINE MODULES
# =========================================

from handlers.error_handler import handle_errors, validate_file_type
from upload_logic import upload_file
from validation.classifier import classify_dataset
from validation.validator import validate_profiles, validate_performance, validate_attendance
from cleaning_logic.Student_profiles import clean_student_profiles
from cleaning_logic.Student_performance import clean_student_performance
from cleaning_logic.Student_attendance import clean_attendance_data


VALIDATE_FN = {
    "profiles": validate_profiles,
    "performance": validate_performance,
    "attendance": validate_attendance,
}

CLEAN_FN = {
    "profiles": clean_student_profiles,
    "performance": clean_student_performance,
    "attendance": clean_attendance_data,
}


def process_file(file_path: Path):
    print("\n" + "=" * 80)
    print(f"PROCESSING: {file_path.name}")
    print("=" * 80)

    handle_errors(validate_file_type, file_path)

    saved_file = handle_errors(upload_file, file_path)
    if saved_file is None:
        print("Upload failed. Skipping file.")
        return

    dataset_type = handle_errors(classify_dataset, saved_file)
    if dataset_type is None:
        print("Dataset classification failed. Skipping file.")
        return

    df = pd.read_csv(saved_file)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_", regex=False)

    handle_errors(VALIDATE_FN[dataset_type], df)
    handle_errors(CLEAN_FN[dataset_type], saved_file)

    print(f"Finished processing {file_path.name} as {dataset_type}.")


def main():
    uploaded_files = sorted(UPLOAD_FOLDER.glob("*.csv"))

    if not uploaded_files:
        print(f"No CSV files found in: {UPLOAD_FOLDER}")
        print("Add one or more CSV files to the uploads folder, then run again.")
        return

    print(f"Found {len(uploaded_files)} CSV file(s).")

    for file_path in uploaded_files:
        process_file(file_path)

    print("\nPROJECT PIPELINE COMPLETE.")


if __name__ == "__main__":
    main()
