import pandas as pd
from pathlib import Path


def classify_dataset(data):
    """
    Classify the dataset type based on expected columns.

    Accepts either:
    - a pandas DataFrame
    - a CSV file path
    """

    if isinstance(data, (str, Path)):
        df = pd.read_csv(data)
    else:
        df = data

    profiles_columns = {
        "student_id", "student_name", "class", "gender", "guardian_contact"
    }

    performance_columns = {
        "record_id", "student_id", "student_name", "class", "gender", "term",
        "subject", "attendance_percent", "assignment_score", "quiz_score",
        "exam_score", "total_score", "result", "study_hours", "teacher_comment"
    }

    attendance_columns = {
        "attendance_id", "student_id", "student_name", "class", "term",
        "days_present", "days_absent", "total_school_days", "attendance_percent"
    }

    columns = set(
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )

    if columns == profiles_columns:
        return "profiles"

    if columns == performance_columns:
        return "performance"

    if columns == attendance_columns:
        return "attendance"

    raise ValueError(
        "Unknown dataset format. Columns do not match profiles, performance, or attendance. "
        f"Columns found: {sorted(columns)}"
    )
