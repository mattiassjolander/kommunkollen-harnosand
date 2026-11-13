"""Schemat för automatisk insamling (kravspec 11.1): vissa dagar i månaden vid ett klockslag, svensk tid."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

SVERIGE = ZoneInfo("Europe/Stockholm")


@dataclass(frozen=True)
class Schema:
    dagar: tuple[int, ...]
    klockan: time

    @classmethod
    def fran_miljo(cls) -> Schema | None:
        """INSAMLING_DAGAR (standard "1,15") och INSAMLING_KLOCKAN (standard "03:00"). Tomma dagar stänger av schemat."""
        dagar_text = os.environ.get("INSAMLING_DAGAR", "1,15")
        if not dagar_text.strip():
            return None
        try:
            dagar = tuple(sorted({int(d) for d in dagar_text.split(",") if d.strip()}))
            if not dagar or not all(1 <= d <= 31 for d in dagar):
                raise ValueError
        except ValueError:
            raise ValueError(f"INSAMLING_DAGAR ska vara dagar 1–31 med komma emellan, inte {dagar_text!r}") from None
        klockan_text = os.environ.get("INSAMLING_KLOCKAN", "03:00")
        try:
            klockan = time.fromisoformat(klockan_text.strip())
        except ValueError:
            raise ValueError(f"INSAMLING_KLOCKAN ska vara HH:MM, inte {klockan_text!r}") from None
        return cls(dagar=dagar, klockan=klockan)

    def _tidpunkter(self, fran: datetime, steg: int):
        dag = fran.astimezone(SVERIGE).date()
        for _ in range(400):
            if dag.day in self.dagar:
                yield datetime.combine(dag, self.klockan, tzinfo=SVERIGE)
            dag += timedelta(days=steg)

    def nasta(self, nu: datetime) -> datetime:
        """Nästa planerade tidpunkt efter `nu`."""
        return next(t for t in self._tidpunkter(nu, 1) if t > nu)

    def senaste(self, nu: datetime) -> datetime:
        """Senaste planerade tidpunkt som har passerat (eller är precis nu)."""
        return next(t for t in self._tidpunkter(nu, -1) if t <= nu)
