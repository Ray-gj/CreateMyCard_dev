"""校验器内部的受控融球参考几何，不参与生成或转换。"""

from dataclasses import dataclass

FUSION_REFERENCE_SIZE = 160


@dataclass(frozen=True)
class FusionBallGeometry:
    slot_id: str
    ball_id: str
    width: int
    height: int
    diameter: int
    alignment: str


LARGE_BALL = FusionBallGeometry("fusionBallLargeSlot", "fusionBallLarge", 180, 44, 210, "center")
MEDIUM_BALL = FusionBallGeometry("fusionBallMediumSlot", "fusionBallMedium", 80, 220, 160, "bottom")
SMALL_BALL = FusionBallGeometry(
    "fusionBallSmallSlot", "fusionBallSmall", 195, 190, 100, "bottomEnd"
)
FUSION_BALL_GEOMETRIES = (LARGE_BALL, MEDIUM_BALL, SMALL_BALL)
