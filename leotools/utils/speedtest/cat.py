"""Animacion ASCII del gato segun la velocidad de descarga."""

from dataclasses import dataclass

IDLE_FRAMES = [
    r"""  /\_/\
 ( -.- )   zZ
  > ^ <""",
    r"""  /\_/\
 ( -.- )  zZ
  > ^ <""",
    r"""  /\_/\
 ( -.- )
  > ^ <   zZ""",
]

WALK_FRAMES = [
    r"""  /\_/\
 ( o.o )
  > ^ <""",
    r"""  /\_/\
 ( o.o )_
  > ^ <""",
    r""" _/\_/\
 ( o.o )
  > ^ <""",
    r"""  /\_/\
 ( o.o )/
  > ^ <""",
]

FAST_FRAMES = [
    r""" ~  /\_/\  ~
   ( o.o )
    > ^ <""",
    r"""~~  /\_/\  ~~
   ( o.o )_
    > ^ <""",
    r""" ~ _/\_/\ ~
   ( o.o )
    > ^ <""",
    r"""~~  /\_/\  ~~
   ( o.o )/
   ﾉ > ^ <""",
]

BARS = "▁▂▃▄▅▆▇█"


@dataclass(frozen=True)
class CatTier:
    key: str
    label: str
    color: str
    fps: float


TIERS = {
    "idle": CatTier("idle", "durmiendo", "dim", 2.0),
    "slow": CatTier("slow", "caminando", "green", 5.0),
    "medium": CatTier("medium", "trotando", "cyan", 9.0),
    "fast": CatTier("fast", "corriendo", "yellow", 13.0),
    "turbo": CatTier("turbo", "a toda velocidad", "bold red", 16.0),
}


def tier_for(mbps: float) -> CatTier:
    value = max(0.0, mbps or 0.0)
    if value < 1:
        return TIERS["idle"]
    if value < 20:
        return TIERS["slow"]
    if value < 100:
        return TIERS["medium"]
    if value < 300:
        return TIERS["fast"]
    return TIERS["turbo"]


def frame_for(tier: CatTier, step: int) -> str:
    if tier.key == "idle":
        frames = IDLE_FRAMES
    elif tier.key in ("fast", "turbo"):
        frames = FAST_FRAMES
    else:
        frames = WALK_FRAMES
    return frames[step % len(frames)]


def sparkline(values: list[float], width: int = 60) -> str:
    values = [max(0.0, value) for value in values][-width:]
    if not values:
        return ""
    peak = max(values) or 1.0
    line = "".join(BARS[min(len(BARS) - 1, int(value / peak * (len(BARS) - 1)))] for value in values)
    return " " * max(0, width - len(line)) + line
