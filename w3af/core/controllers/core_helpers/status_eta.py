"""
ETA calculation for scan consumers.
"""

from dataclasses import dataclass

AUDIT = "audit"
CRAWL = "crawl"
GREP = "grep"


@dataclass(frozen=True)
class Adjustment:
    """Ratios used to compensate for known and unknown queue work."""

    known: float = 1.0
    unknown: float = 1.0
    average: bool = True


class EtaCalculator:
    """Calculate queue completion times without scan infrastructure."""

    def __init__(self):
        self._eta_smooth = {AUDIT: 0.0, GREP: 0.0, CRAWL: 0.0}

    def calculate(self, input_speed, output_speed, queue_size, phase, adjustment):
        if output_speed == 0 and input_speed == 0:
            return 0.0

        if output_speed == 0 and input_speed != 0:
            return 5 * 60.0

        if input_speed >= output_speed:
            t_queued = (queue_size / output_speed) * adjustment.known
            t_new = (input_speed * t_queued / output_speed) * adjustment.unknown
            eta_minutes = t_queued + t_new
        else:
            t_queued = queue_size / output_speed
            t_new = input_speed * t_queued / output_speed
            eta_minutes = (t_queued + t_new) * adjustment.known

        eta = eta_minutes * 60
        if adjustment.average:
            eta = eta * 3 / 4 + self._eta_smooth[phase] * 1 / 4
            self._eta_smooth[phase] = eta

        return eta
