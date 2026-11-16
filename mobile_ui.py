"""Backward-compatible import entry; active UI lives in ui.navigation."""
from ui.navigation import main
from services.dispatch import select_hospital
from services.events import handle_event


