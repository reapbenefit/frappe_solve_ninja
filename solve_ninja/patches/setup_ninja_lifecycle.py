"""Set initial Ninja Level / Status for existing profiles from their event history."""

from solve_ninja.services.ninja_mis import initialise_lifecycle

# Levels and statuses start as of the end of October 2026, so October is the first snapshot month
SETUP_AS_OF = "2026-10-31 23:59:59"


def execute():
	initialise_lifecycle(as_of=SETUP_AS_OF)
