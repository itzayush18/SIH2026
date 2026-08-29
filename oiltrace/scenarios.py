"""Named scenarios — the hackathon replay reel.

Every scenario runs through the *same* production pipeline (SAR simulator +
detect + drift + inversion + attribution). Nothing is a hand-cut fake for the
demo; the parameters differ, the physics does not — per spec §35 and §56.
"""
from __future__ import annotations

from dataclasses import dataclass
from sagar.core.geoutil import Origin

DEFAULT_ORIGIN = Origin(19.35, 71.80)


@dataclass
class Scenario:
    slug: str
    name: str
    subtitle: str
    seed: int
    origin: Origin
    difficulty: str
    story: str
    tags: tuple


SCENARIOS = [
    Scenario("arabian-tanker", "OIL-2026-0042 · MT KAVERI STAR",
             "High-confidence tanker discharge · Arabian Sea",
             seed=11, origin=Origin(19.35, 71.80), difficulty="canonical",
             story="A tanker slows, alters course, goes AIS-dark for 44 min, "
                   "then resumes transit. Inversion recovers the source track to 2 km / 23 min.",
             tags=("high-confidence", "AIS-gap", "tanker", "prime-suspect")),
    Scenario("bay-of-bengal", "OIL-2026-0041 · MV ARGOSY",
             "Cargo · Bay of Bengal · night acquisition",
             seed=53, origin=Origin(15.6, 82.4), difficulty="hard",
             story="Weaker drift signal, more ambiguous slick geometry. "
                   "Inversion IoU falls to ~0.4 but attribution still holds.",
             tags=("medium-confidence", "cargo", "wide-search")),
    Scenario("laccadive-fishing", "OIL-2026-0040 · look-alike",
             "Suspected look-alike · Laccadive Sea",
             seed=32, origin=Origin(11.8, 73.2), difficulty="skeptical",
             story="A dark biogenic film — soft edges, low contrast. "
                   "The classifier should reject it or return low P(oil).",
             tags=("look-alike", "false-positive-test")),
    Scenario("gulf-of-kutch", "OIL-2026-0039 · nearshore",
             "Nearshore spill · Gulf of Kutch · sensitive coast",
             seed=25, origin=Origin(22.6, 68.8), difficulty="urgent",
             story="Near-shore discharge in an ecologically sensitive zone. "
                   "The forecast puts the leading edge onto the mangroves within 18 h.",
             tags=("nearshore", "coastal-risk", "urgent")),
    Scenario("andaman-quiet", "OIL-2026-0038 · quiet transit",
             "Clean transit · Andaman approaches",
             seed=39, origin=Origin(12.4, 92.9), difficulty="hard",
             story="Multiple vessels transit the origin envelope with clean AIS. "
                   "Only the source-track match separates the true polluter from the decoys.",
             tags=("multiple-vessels", "clean-AIS")),
    Scenario("stormy-scene", "OIL-2026-0037 · high-wind",
             "Stormy sea · 12 m/s wind · reduced Bragg background",
             seed=74, origin=Origin(20.9, 70.6), difficulty="hard",
             story="High wind mixes the slick, reducing damping contrast. "
                   "Segmentation IoU drops; the pipeline continues under a downgraded confidence.",
             tags=("stormy", "low-contrast", "degraded")),
]

BY_SLUG = {s.slug: s for s in SCENARIOS}
