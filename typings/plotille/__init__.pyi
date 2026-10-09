import os
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal, Protocol

type DataValue = float | int | datetime
type DataValues = Sequence[float | int] | Sequence[datetime]
type ColorMode = Literal["names", "byte", "rgb"]
type ColorDefinition = str | int | tuple[int, int, int] | None

class Formatter(Protocol):
    def __call__(self, val: Any, chars: int, delta: Any, left: bool) -> str: ...

class Figure:
    x_label: str
    y_label: str
    def __init__(self) -> None: ...
    @property
    def width(self) -> int: ...
    @width.setter
    def width(self, value: int) -> None: ...
    @property
    def height(self) -> int: ...
    @height.setter
    def height(self, value: int) -> None: ...
    @property
    def color_mode(self) -> ColorMode: ...
    @color_mode.setter
    def color_mode(self, value: ColorMode) -> None: ...
    def register_label_formatter(
        self, type_: type[Any], formatter: Formatter
    ) -> None: ...
    def set_x_limits(
        self, min_: DataValue | None = None, max_: DataValue | None = None
    ) -> None: ...
    def set_y_limits(
        self, min_: DataValue | None = None, max_: DataValue | None = None
    ) -> None: ...
    def plot(
        self,
        X: DataValues,
        Y: DataValues,
        lc: ColorDefinition = None,
        interp: Literal["linear"] | None = "linear",
        label: str | None = None,
        marker: str | None = None,
    ) -> None: ...
    def show(self, legend: bool = False) -> str: ...

def hist(
    X: DataValues,
    bins: int = 40,
    width: int = 80,
    log_scale: bool = False,
    linesep: str = os.linesep,
    lc: ColorDefinition = None,
    bg: ColorDefinition = None,
    color_mode: ColorMode = "names",
) -> str: ...
