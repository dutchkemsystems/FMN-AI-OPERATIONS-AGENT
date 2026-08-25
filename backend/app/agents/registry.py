"""Agent registry — builds and wires all agent instances."""
from __future__ import annotations

from typing import Any

from .supply_chain_agent import SupplyChainAgent
from .energy_agent import EnergyAgent
from .logistics_agent import LogisticsAgent
from .silo_agent import SiloAgent
from .waste_agent import WasteAgent
from .vision_agent import VisionAgent
from .security_agent import SecurityAgent
from .orchestrator_agent import OrchestratorAgent
from ..vision.camera_manager import CameraManager
from ..vision.detector import Detector


def build_agents(
    settings: Any,
    session_factory: Any,
    bus: Any = None,
    ledger: Any = None,
    cameras: CameraManager | None = None,
    detector: Detector | None = None,
) -> dict[str, Any]:
    common = dict(settings=settings, session_factory=session_factory, bus=bus, ledger=ledger)
    agents: dict[str, Any] = {}

    agents["supply_chain"] = SupplyChainAgent(**common)
    agents["energy"] = EnergyAgent(**common)
    agents["logistics"] = LogisticsAgent(**common)
    agents["silo"] = SiloAgent(**common)
    agents["waste"] = WasteAgent(**common)

    if settings.use_vision:
        cameras = cameras or CameraManager()
        detector = detector or Detector()
        agents["vision"] = VisionAgent(**common, cameras=cameras, detector=detector)

    agents["security"] = SecurityAgent(**common)
    agents["orchestrator"] = OrchestratorAgent(**common, agents=agents)

    return agents
