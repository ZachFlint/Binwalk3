"""Block entropy analysis with binwalk v2 semantics."""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from binwalk._errors import ModuleException

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_BLOCK_SIZE = 1024
DEFAULT_DATA_POINTS = 2048
DEFAULT_TRIGGER_HIGH = 0.95
DEFAULT_TRIGGER_LOW = 0.85
_BITS_PER_BYTE = 8
_ZLIB_LEVEL = 9
_MARKER_COLORS = ("r", "g", "c", "b", "m")


@dataclass(frozen=True)
class EntropyBlock:
    """Entropy of one block of a file.

    Attributes:
        offset: Offset of the block's first byte.
        size: Number of bytes in the block.
        entropy: Entropy normalized to 0..1 (binwalk v2 scale).
        description: ``Rising entropy edge (x)``, ``Falling entropy edge (x)`` or the value.
        display: Whether binwalk v2 would print this block.
    """

    offset: int
    size: int
    entropy: float
    description: str
    display: bool

    @property
    def entropy_bits(self) -> float:
        """Return the entropy in bits per byte (0..8), the scale binwalk v3 reports.

        Returns:
            Entropy multiplied by 8.
        """
        return self.entropy * _BITS_PER_BYTE


def shannon(data: bytes) -> float:
    """Compute Shannon entropy normalized to 0..1.

    Args:
        data: Bytes to measure.

    Returns:
        Entropy in bits per byte divided by 8; 0.0 for empty input.
    """
    length = len(data)
    if length == 0:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    entropy = 0.0
    for count in counts:
        if count:
            probability = count / length
            entropy -= probability * math.log2(probability)
    return entropy / _BITS_PER_BYTE


def zlib_ratio(data: bytes) -> float:
    """Estimate entropy as the zlib compression ratio, capped at 1.0.

    This is binwalk v2's ``--fast`` (``use_zlib``) algorithm.

    Args:
        data: Bytes to measure.

    Returns:
        ``len(zlib.compress(data, 9)) / len(data)``, capped at 1.0; 0.0 for empty input.
    """
    if not data:
        return 0.0
    return min(len(zlib.compress(data, _ZLIB_LEVEL)) / len(data), 1.0)


def v2_block_size(file_size: int) -> int:
    """Return binwalk v2's default entropy block size for a file.

    The file is divided into 2048 data points and the block size is rounded up to the next
    multiple of 1024, with 1024 as the minimum.

    Args:
        file_size: Size of the file in bytes.

    Returns:
        Block size in bytes.
    """
    raw = file_size / DEFAULT_DATA_POINTS
    block_size = int(raw + ((DEFAULT_BLOCK_SIZE - raw) % DEFAULT_BLOCK_SIZE))
    return block_size if block_size > 0 else DEFAULT_BLOCK_SIZE


@dataclass(frozen=True)
class EntropySettings:
    """Options for entropy analysis, using binwalk v2 names and defaults.

    Attributes:
        block_size: Bytes per block; 0 or None selects ``v2_block_size``.
        trigger_high: Rising-edge threshold on the 0..1 scale.
        trigger_low: Falling-edge threshold on the 0..1 scale.
        use_zlib: Use the zlib compression ratio instead of Shannon entropy.
        verbose: Mark every block for display instead of only edges.
        display_results: Value of ``display`` for blocks binwalk v2 would print.
    """

    block_size: int | None = None
    trigger_high: float = DEFAULT_TRIGGER_HIGH
    trigger_low: float = DEFAULT_TRIGGER_LOW
    use_zlib: bool = False
    verbose: bool = False
    display_results: bool = True


def analyze(data: bytes, settings: EntropySettings | None = None) -> list[EntropyBlock]:
    """Split data into blocks and compute each block's entropy and edge classification.

    Edge detection follows binwalk v2: a rising edge is reported when entropy reaches
    ``trigger_high`` after having been below it, and a falling edge when it drops to
    ``trigger_low`` after having been above it.

    Args:
        data: File contents.
        settings: Analysis options; defaults match binwalk v2.

    Returns:
        One EntropyBlock per block, in file order.
    """
    options = settings or EntropySettings()
    block_size = (
        options.block_size
        if options.block_size and options.block_size > 0
        else v2_block_size(len(data))
    )
    measure = zlib_ratio if options.use_zlib else shannon
    blocks: list[EntropyBlock] = []
    last_edge: int | None = None
    trigger_reset = True
    for offset in range(0, len(data), block_size):
        chunk = data[offset : offset + block_size]
        entropy = measure(chunk)
        display = options.display_results
        description = f"{entropy:f}"
        if not options.verbose:
            if (last_edge in (None, 0) and entropy > options.trigger_low) or (
                last_edge in (None, 1) and entropy < options.trigger_high
            ):
                trigger_reset = True
            if trigger_reset and entropy >= options.trigger_high:
                description = f"Rising entropy edge ({entropy:f})"
                last_edge = 1
                trigger_reset = False
            elif trigger_reset and entropy <= options.trigger_low:
                description = f"Falling entropy edge ({entropy:f})"
                last_edge = 0
                trigger_reset = False
            else:
                display = False
        blocks.append(EntropyBlock(offset, len(chunk), entropy, description, display))
    return blocks


def plot_path(file_path: str | Path, directory: str | Path | None = None) -> Path:
    """Return where binwalk v2 saves an entropy plot: ``<cwd>/<basename>.png``.

    Args:
        file_path: The analyzed file.
        directory: Directory to save into; defaults to the current working directory.

    Returns:
        Output path for the PNG.
    """
    base = Path(directory) if directory is not None else Path.cwd()
    return base / f"{Path(file_path).name}.png"


def save_plot(
    blocks: Sequence[EntropyBlock],
    output: Path,
    markers: Sequence[tuple[int, str]] = (),
    *,
    title: str = "Entropy",
) -> Path:
    """Render an entropy graph to a PNG file with matplotlib.

    The figure is drawn with the Agg canvas directly and never touches pyplot's global state,
    so it is safe to call from GUI applications.

    Args:
        blocks: Entropy blocks to plot.
        output: PNG path to write.
        markers: ``(offset, description)`` pairs drawn as vertical lines with a legend.
        title: Figure title.

    Returns:
        The written path.

    Raises:
        ModuleException: If matplotlib is not installed.
    """
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError as exc:
        message = "Saving entropy plots requires matplotlib: pip install binwalk3[plot]"
        raise ModuleException(message) from exc

    figure = Figure()
    FigureCanvasAgg(figure)
    axes = cast("_Axes", figure.add_subplot(1, 1, 1, facecolor="black"))
    axes.set_title(title)
    axes.set_xlabel("Offset")
    axes.set_ylabel("Entropy")
    xs = [block.offset for block in blocks]
    ys = [block.entropy for block in blocks]
    axes.plot(xs, ys, "y", lw=2)
    axes.set_ylim(0, 1.1)
    colors: dict[str, str] = {}
    for offset, description in markers:
        label: str | None = None
        if description not in colors:
            colors[description] = _MARKER_COLORS[len(colors) % len(_MARKER_COLORS)]
            label = description
        axes.plot([offset, offset], [0, 1.1], f"{colors[description]}-", lw=2, label=label)
    if colors:
        axes.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    output.parent.mkdir(parents=True, exist_ok=True)
    cast("_Figure", figure).savefig(str(output), bbox_inches="tight")
    return output


class _Axes(Protocol):
    def set_title(self, label: str) -> object: ...
    def set_xlabel(self, xlabel: str) -> object: ...
    def set_ylabel(self, ylabel: str) -> object: ...
    def set_ylim(self, bottom: float, top: float) -> object: ...
    def plot(
        self,
        xs: Sequence[float],
        ys: Sequence[float],
        fmt: str,
        *,
        lw: float,
        label: str | None = None,
    ) -> object: ...
    def legend(self, *, loc: str, bbox_to_anchor: tuple[float, float]) -> object: ...


class _Figure(Protocol):
    def savefig(self, fname: str, *, bbox_inches: str) -> None: ...
