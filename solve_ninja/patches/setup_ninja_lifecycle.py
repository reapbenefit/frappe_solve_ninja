"""Set initial Ninja Level / Status for existing profiles from their event history."""

from solve_ninja.services.ninja_mis import initialise_lifecycle


def execute():
	initialise_lifecycle()
