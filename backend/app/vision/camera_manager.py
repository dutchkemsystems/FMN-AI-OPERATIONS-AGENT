"""Camera registry with graceful synthetic frames when no physical device exists."""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass

@dataclass
class Camera:
    camera_id: str
    name: str
    source: str
    location: str

class CameraManager:
    def __init__(self) -> None:
        self._cameras: dict[str, Camera] = {}

    def register(self, camera_id: str, name: str, source: str = "synthetic", location: str = "") -> Camera:
        cam = Camera(camera_id=camera_id, name=name, source=source, location=location)
        self._cameras[camera_id] = cam
        return cam

    def list(self) -> list[Camera]:
        return list(self._cameras.values())

    def get(self, camera_id: str) -> Camera | None:
        return self._cameras.get(camera_id)

    def capture(self, camera_id: str) -> np.ndarray:
        cam = self._cameras.get(camera_id)
        if not cam:
            raise KeyError(f"Camera {camera_id} not registered")
        if cam.source == "synthetic" or not cam.source.isdigit():
            return self._synthetic_frame(camera_id)
        import cv2
        cap = cv2.VideoCapture(int(cam.source))
        ok, frame = cap.read()
        cap.release()
        if ok:
            return frame
        return self._synthetic_frame(camera_id)

    @staticmethod
    def _synthetic_frame(camera_id: str) -> np.ndarray:
        rng = np.random.default_rng(abs(hash(camera_id)) % (2**32))
        frame = rng.integers(40, 60, size=(480, 640, 3), dtype=np.uint8)
        frame[:, 300:500, :] = 220
        return frame
