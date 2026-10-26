from decimal import Decimal, InvalidOperation

MAX_COURSEWORK = 40
MAX_EXAM = 60

# (minimum total mark, letter grade, grade point), highest first
SCALE = [
    (80, "A", 5.0),
    (75, "B+", 4.5),
    (70, "B", 4.0),
    (65, "C+", 3.5),
    (60, "C", 3.0),
    (55, "D+", 2.5),
    (50, "D", 2.0),
    (0, "E", 0.0),
]


def parse_mark(raw, maximum, label):
    """Turn form input into a Decimal between 0 and `maximum`, or raise ValueError."""
    try:
        value = Decimal((raw or "").strip())
    except InvalidOperation:
        raise ValueError(f"{label} must be a number.") from None
    if not value.is_finite():
        raise ValueError(f"{label} must be a number.")
    if value < 0 or value > maximum:
        raise ValueError(f"{label} must be between 0 and {maximum}.")
    return value.quantize(Decimal("0.01"))


def compute_grade(total):
    """Return (letter, grade_point) for a total mark."""
    for floor, letter, points in SCALE:
        if total >= floor:
            return letter, points
    return "E", 0.0


def gpa(rows):
    """Credit-weighted GPA for rows that have `grade_point` and `credit_units`."""
    units = sum(r["credit_units"] for r in rows)
    if not units:
        return None
    points = sum(float(r["grade_point"]) * r["credit_units"] for r in rows)
    return round(points / units, 2)
