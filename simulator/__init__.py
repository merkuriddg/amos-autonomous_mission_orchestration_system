"""AMOS Simulator — scenario management and simulation utilities.

The simulation tick loop (sim_tick) lives in web/app.py due to deep
coupling with Flask globals.  This package provides:
  • ScenarioLoader  – load / list / validate scenario configs
  • DEFAULT_SCENARIOS – built-in scenario catalog
"""

from simulator.scenarios import ScenarioLoader, DEFAULT_SCENARIOS

__all__ = ["ScenarioLoader", "DEFAULT_SCENARIOS"]
