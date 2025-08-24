from typing import Dict, Any


def get_user_info(user_id: str) -> Dict[str, Any]:
    # Simulated user profile store
    # In a real app, replace with DB/HTTP call
    return {
        "user_id": user_id,
        "status": "active",
        "limits": {"daily_transfer": 5000},
        "kyc": {"level": "basic"},
        "flags": [],
    }
