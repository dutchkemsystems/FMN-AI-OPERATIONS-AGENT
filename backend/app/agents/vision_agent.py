"""Quality Vision Agent.

Uses computer vision (YOLOv8 or OpenCV heuristic) on camera feeds to
detect production defects and log anomalies.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..blockchain.events import record_event
from ..models.database import VisionEvent
from .base_agent import Action, BaseAgent


class VisionAgent(BaseAgent):
    agent_type = "vision"
    description = "Camera-based quality inspection and defect detection"
    interval_seconds = 60

    def __init__(
        self, settings: Any, session_factory: Any = None, bus: Any = None,
        ledger: Any = None, cameras: Any = None, detector: Any = None, **kwargs: Any,
    ) -> None:
        super().__init__(settings, session_factory, bus, ledger, **kwargs)
        self.cameras = cameras
        self.detector = detector

    def observe(self, db: Session) -> dict:
        if not self.cameras or not self.detector:
            return {"cameras": [], "detections": []}

        all_detections: list[dict] = []
        for cam in self.cameras.list():
            try:
                frame = self.cameras.capture(cam.camera_id)
                dets = self.detector.detect(frame)
                for d in dets:
                    all_detections.append(
                        {
                            "camera_id": cam.camera_id,
                            "label": d.label,
                            "confidence": round(d.confidence, 3),
                            "bbox": list(d.bbox) if hasattr(d, "bbox") else [],
                        }
                    )
            except Exception as exc:
                self.logger.debug("capture from %s failed: %s", cam.camera_id, exc)

        return {
            "cameras": [c.camera_id for c in self.cameras.list()],
            "detections": all_detections,
        }

    def think(self, observation: dict) -> list[Action]:
        actions: list[Action] = []
        confidence_threshold = 0.65

        for det in observation.get("detections", []):
            if det["confidence"] < confidence_threshold:
                continue

            label = det["label"].lower()
            if "person" in label or "intruder" in label:
                actions.append(
                    Action(
                        action_type="flag_intrusion",
                        description=f"Person detected on camera {det['camera_id']}",
                        params={
                            "camera_id": det["camera_id"],
                            "label": det["label"],
                            "confidence": det["confidence"],
                            "bbox": det["bbox"],
                        },
                    )
                )
            elif any(kw in label for kw in ("flour", "bag", "defect", "damage", "object")):
                actions.append(
                    Action(
                        action_type="flag_defect",
                        description=f"Potential defect on camera {det['camera_id']}: {det['label']}",
                        params={
                            "camera_id": det["camera_id"],
                            "label": det["label"],
                            "confidence": det["confidence"],
                            "bbox": det["bbox"],
                        },
                    )
                )

        return actions

    def perform_action(self, action: Action, db: Session) -> dict:
        is_intrusion = "intrusion" in action.action_type
        event_type = "intrusion" if is_intrusion else "quality_flag"
        bucket = self.settings.s3_bucket or "local"

        event = VisionEvent(
            camera_id=action.params.get("camera_id", ""),
            event_type=event_type,
            image_url=f"s3://{bucket}/{action.params.get('camera_id', '')}/{utcnow_ts()}.jpg",
            confidence=action.params.get("confidence", 0),
            bounding_boxes=[action.params] if action.params.get("bbox") else None,
        )
        db.add(event)

        if self.ledger:
            record_event(
                self.ledger,
                db,
                "security_event" if is_intrusion else "quality_check",
                {"camera": action.params.get("camera_id"), "label": action.params.get("label")},
            )

        return {"flagged": True, "event_type": event_type}


def utcnow_ts() -> str:
    from ..utils.helpers import utcnow

    return utcnow().strftime("%Y%m%d%H%M%S")
