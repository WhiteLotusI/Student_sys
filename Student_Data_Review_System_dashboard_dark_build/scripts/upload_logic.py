from pathlib import Path
import shutil
from datetime import datetime


# =========================================
# PROJECT PATHS
# =========================================

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def upload_file(source_path=None):
    """
    Save one CSV file into data/raw and return the saved path.

    Works in two modes:
    1. CLI/manual mode: upload_file() asks the user for a file path.
    2. Batch mode: upload_file(file_path) receives a file path from run_all.py.
    """

    if source_path is None:
        source_path = input("\nEnter CSV file path: ").strip()

    source_path = Path(source_path)

    if not source_path.exists():
        raise FileNotFoundError(f"File not found:\n{source_path}")

    if source_path.suffix.lower() != ".csv":
        raise ValueError("Invalid file type. Only CSV files are supported.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    clean_name = f"{source_path.stem}_{timestamp}.csv"
    destination_path = RAW_DIR / clean_name

    shutil.copy2(source_path, destination_path)

    print("\nFile uploaded successfully.")
    print(f"Saved to:\n{destination_path}")

    return destination_path


def upload_multiple_files(file_paths):
    """
    Save multiple CSV files into data/raw.
    Returns a list of saved file paths.
    """

    saved_files = []

    for file_path in file_paths:
        saved_files.append(upload_file(file_path))

    return saved_files
