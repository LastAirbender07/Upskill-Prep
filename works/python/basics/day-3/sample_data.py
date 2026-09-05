"""
Sample event data — separated from models.

Day-2 had sample data + print calls inside schema.py, which meant
they executed every time the file was imported (including when FastAPI started).
Now this only runs when you explicitly `python sample_data.py`.
"""

from datetime import datetime, timezone

from models import EventType, debug_event


# --- Sample events ---

event_1 = {
    "id": 123,
    "user_id": 42,
    "metadata": {"amount": 1299.50},
}

event_2 = {
    "id": 124,
    "type": EventType.checkout,  # StrEnum — no need for .value anymore
    "user_id": 78,
    "timestamp": datetime.now(tz=timezone.utc),  # UTC-aware
    "metadata": {"amount": 1299.50},
}

# Bad event — will raise a validation error (id=0 violates gt=0)
event_bad = {
    "id": 0,
    "user_id": -5,
    "metadata": {"amount": 100},
}


# --- Only runs when executed directly, NOT on import ---

if __name__ == "__main__":
    print("=== Valid events ===\n")
    debug_event(event_1)
    debug_event(event_2)

    print("=== Invalid event (should raise error) ===\n")
    try:
        debug_event(event_bad)
    except Exception as e:
        # We let the error propagate and catch it HERE — not inside the function.
        # This way you actually SEE what went wrong.
        print(f"Validation failed (as expected):\n{e}\n")
