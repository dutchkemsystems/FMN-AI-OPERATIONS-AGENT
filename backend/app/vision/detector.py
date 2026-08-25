"""Object / defect detection with YOLOv8 when available, OpenCV heuristic fallback."""
from __future__ import annotations
import logging
from dataclasses import dataclass

logger = logging.getLogger("fmn.vision")

@dataclass
class Detection:
    label: str
    confidence: float
    bbox: tuple
    def as_dict(self) -> dict:
        return {"label": self.label, "confidence": self.confidence, "bbox": list(self.bbox)}

class Detector:
    LABEL_MAP = {
        "person": "person", "intruder": "person",
        "flour bag": "flour_bag", "bag": "flour_bag",
        "defect": "defect", "damage": "defect",
    }
    def __init__(self, model_path: str | None = None, confidence_threshold: float = 0.55) -> None:
        self._model = None
        self._threshold = confidence_threshold
        if model_path:
            try:
                from ultralytics import YOLO
                self._model = YOLO(model_path)
            except Exception:
                logger.warning("YOLO weights unavailable; heuristic detector active")

    def detect(self, frame) -> list[Detection]:
        if self._model is not None:
            return self._detect_yolo(frame)
        return self._detect_heuristic(frame)

    def _detect_yolo(self, frame) -> list[Detection]:
        results = self._model.predict(frame, verbose=False)[0]
        detections = []
        for box in results.boxes:
            conf = float(box.conf[0])
            if conf < self._threshold:
                continue
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            raw_label = results.names[int(box.cls[0])]
            label = self.LABEL_MAP.get(raw_label, raw_label)
            detections.append(Detection(label, conf, (x1, y1, x2 - x1, y2 - y1)))
        return detections

    def _detect_heuristic(self, frame) -> list[Detection]:
        try:
            import cv2
        except ImportError:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = gray.shape[:2]
        detections = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < w * h * 0.005:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            aspect = bw / max(bh, 1)
            vertical_center = (y + bh / 2) / h
            if aspect < 0.8 and vertical_center > 0.5:
                label, conf = "person", 0.72
            elif aspect > 1.6:
                label, conf = "flour_bag", 0.68
            else:
                label, conf = "object", 0.6
            detections.append(Detection(label, conf, (x, y, bw, bh)))
        return detections[:20]
