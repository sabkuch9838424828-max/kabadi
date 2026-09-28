"""Material image classifier.

Architecture (per documentation section 5.D.1 — transfer learning):
  * Backbone: MobileNetV3-Small, ImageNet-pretrained (torchvision).
  * Head: either (a) a fine-tuned linear head loaded from MODEL_PATH, or
    (b) a documented ImageNet-class -> e-waste-category aggregation layer.

This is genuine model inference on real pretrained weights. It is explicitly an
*estimate*: the response carries confidence, the model name, and a disclaimer,
and the collector is always able to override the suggested category, because no
classifier can identify a material with laboratory certainty from one photo.
"""
from __future__ import annotations

import io
import threading

from PIL import Image

from app.core.config import get_settings

settings = get_settings()

# ImageNet class-name fragments mapped to our e-waste categories.
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "CRT": ("television", "cathode", "screen", "monitor"),
    "LCD": ("monitor", "screen", "television", "laptop", "notebook", "tablet", "ipod"),
    "PCB": ("circuit", "motherboard", "microchip", "chip", "processor"),
    "battery": ("battery", "accumulator", "power pack"),
    "cable": ("cable", "coil", "chain", "rope", "wire"),
    "motor_magnet": ("electric fan", "fan", "magnet", "motor", "loudspeaker", "speaker"),
    "mixed_plastic": (
        "plastic bag",
        "water bottle",
        "pill bottle",
        "carton",
        "cup",
        "bucket",
    ),
    "other": (
        "computer",
        "keyboard",
        "mouse",
        "printer",
        "radio",
        "cellular",
        "phone",
        "remote control",
        "modem",
        "hard disc",
        "cd player",
        "cassette",
        "microwave",
        "refrigerator",
        "washer",
        "dishwasher",
        "toaster",
        "vacuum",
        "heater",
        "hair dryer",
        "clock",
        "camera",
        "projector",
        "joystick",
        "switch",
        "plug",
        "soldering",
    ),
}

CLASSIFIER_DISCLAIMER = (
    "Category suggested by an AI image classifier. This is a best-effort estimate "
    "and not a laboratory identification — please confirm or change the category."
)

_MATCH_THRESHOLD = 0.12


class MaterialClassifier:
    _instance: "MaterialClassifier | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._model = None
        self._weights = None
        self._custom = False
        self._model_name = "unloaded"
        self._load_error: str | None = None

    @classmethod
    def instance(cls) -> "MaterialClassifier":
        with cls._lock:
            if cls._instance is None:
                cls._instance = MaterialClassifier()
                cls._instance._load()
            return cls._instance

    # ------------------------------------------------------------------ load
    def _load(self) -> None:
        try:
            import torch
            import torch.nn as nn
            import torchvision

            from app.core.constants import CATEGORY_CODES

            if settings.model_path:
                backbone = torchvision.models.mobilenet_v3_small(weights=None)
                in_features = backbone.classifier[-1].in_features
                backbone.classifier[-1] = nn.Linear(in_features, len(CATEGORY_CODES))
                state = torch.load(settings.model_path, map_location="cpu")
                backbone.load_state_dict(state)
                backbone.eval()
                self._model = backbone
                self._custom = True
                self._model_name = f"mobilenet_v3_small_finetuned:{settings.model_path}"
                return

            weights = torchvision.models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
            model = torchvision.models.mobilenet_v3_small(weights=weights)
            model.eval()
            self._model = model
            self._weights = weights
            self._model_name = "mobilenet_v3_small_imagenet+ewaste-map"
        except Exception as exc:  # pragma: no cover - environment dependent
            self._load_error = f"{type(exc).__name__}: {exc}"
            self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def load_error(self) -> str | None:
        return self._load_error

    # -------------------------------------------------------------- predict
    def classify(self, image_bytes: bytes) -> dict:
        if not self.available:
            return {
                "material_category": "other",
                "confidence": 0.0,
                "alternatives": [],
                "model": self._model_name,
                "is_estimate": True,
                "disclaimer": CLASSIFIER_DISCLAIMER
                + f" (classifier unavailable: {self._load_error})",
            }

        import torch

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        if self._custom:
            from app.core.constants import CATEGORY_CODES

            transform = self._weights.transform() if self._weights else _default_transform()
            tensor = transform(image).unsqueeze(0)
            with torch.no_grad():
                probs = torch.softmax(self._model(tensor), dim=1)[0]
            scored = {c: float(probs[i]) for i, c in enumerate(CATEGORY_CODES)}
        else:
            with torch.no_grad():
                logits = self._model(self._weights.transforms()(image).unsqueeze(0))
                probs = torch.softmax(logits, dim=1)[0]
            categories = self._weights.meta["categories"]
            scored = self._aggregate(probs.tolist(), categories)

        ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
        top_cat, top_score = ranked[0]
        if top_score < _MATCH_THRESHOLD:
            top_cat, top_score = "other", max(top_score, scored.get("other", 0.0))
            ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)

        return {
            "material_category": top_cat,
            "confidence": round(float(top_score), 4),
            "alternatives": [
                {"material_category": c, "confidence": round(float(s), 4)}
                for c, s in ranked[1:4]
            ],
            "model": self._model_name,
            "is_estimate": True,
            "disclaimer": CLASSIFIER_DISCLAIMER,
        }

    @staticmethod
    def _aggregate(probs: list[float], imagenet_categories: list[str]) -> dict[str, float]:
        scored: dict[str, float] = {c: 0.0 for c in _CATEGORY_KEYWORDS}
        for idx, name in enumerate(imagenet_categories):
            p = probs[idx]
            if p < 1e-4:
                continue
            lowered = name.lower()
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(k in lowered for k in keywords):
                    scored[cat] += p
        return scored


def _default_transform():
    import torchvision

    return torchvision.transforms.Compose(
        [
            torchvision.transforms.Resize(256),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize(
                mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
            ),
        ]
    )
