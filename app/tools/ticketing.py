from typing import Dict, Any


_tickets: Dict[str, Dict[str, Any]] = {}


def open_ticket(user_id: str, category: str, summary: str) -> Dict[str, Any]:
    ticket_id = f"T-{len(_tickets)+1:05d}"
    _tickets[ticket_id] = {
        "id": ticket_id,
        "user_id": user_id,
        "category": category,
        "summary": summary,
        "status": "open",
    }
    return _tickets[ticket_id]


def get_ticket(ticket_id: str) -> Dict[str, Any] | None:
    return _tickets.get(ticket_id)
