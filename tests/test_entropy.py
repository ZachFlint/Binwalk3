"""Entropy analysis: algorithm ground truth and integration through binwalk.scan."""

from __future__ import annotations

import hashlib
import math
import zlib
from pathlib import Path

import pytest

import binwalk
from binwalk import _entropy
from tests.helpers import FIXTURES

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _random_bytes(size: int, seed: int) -> bytes:
    stream = b"".join(
        hashlib.sha256(f"{seed}:{counter}".encode()).digest() for counter in range(size // 32 + 1)
    )
    return stream[:size]


def test_shannon_ground_truth() -> None:
    assert _entropy.shannon(b"") == 0.0
    assert _entropy.shannon(bytes(4096)) == 0.0
    assert _entropy.shannon(bytes(range(256)) * 4) == pytest.approx(1.0)
    assert _entropy.shannon(b"\x00\x01" * 512) == pytest.approx(1 / 8)
    assert _entropy.shannon(bytes(range(16)) * 64) == pytest.approx(4 / 8)


def test_zlib_ratio_matches_definition() -> None:
    data = b"abcabcabd" * 200
    assert _entropy.zlib_ratio(data) == pytest.approx(len(zlib.compress(data, 9)) / len(data))
    assert _entropy.zlib_ratio(_random_bytes(4096, 1)) == 1.0
    assert _entropy.zlib_ratio(b"") == 0.0


@pytest.mark.parametrize(
    "size", [0, 1, 1402, 2048 * 1024, 2048 * 1024 + 1, 2048 * 1500, 50_000_000]
)
def test_v2_block_size_rounds_up_to_1024(size: int) -> None:
    expected = max(1024, math.ceil(size / 2048 / 1024) * 1024)
    assert _entropy.v2_block_size(size) == expected


def test_edge_detection_sequence() -> None:
    data = bytes(4096) + _random_bytes(4096, 2) + bytes(4096)
    blocks = _entropy.analyze(data, _entropy.EntropySettings(block_size=1024))
    assert len(blocks) == 12
    assert [block.offset for block in blocks] == list(range(0, 12288, 1024))
    shown = [(block.offset, block.description.split(" (")[0]) for block in blocks if block.display]
    assert shown == [
        (0, "Falling entropy edge"),
        (4096, "Rising entropy edge"),
        (8192, "Falling entropy edge"),
    ]
    assert blocks[5].description == f"{blocks[5].entropy:f}"
    assert blocks[4].entropy > 0.95


def test_verbose_displays_every_block() -> None:
    data = bytes(2048) + _random_bytes(2048, 3)
    blocks = _entropy.analyze(data, _entropy.EntropySettings(block_size=1024, verbose=True))
    assert all(block.display for block in blocks)
    assert all(block.description == f"{block.entropy:f}" for block in blocks)


def test_custom_triggers() -> None:
    data = bytes(range(16)) * 64
    default = _entropy.analyze(data, _entropy.EntropySettings(block_size=1024))
    lowered = _entropy.analyze(data, _entropy.EntropySettings(block_size=1024, trigger_high=0.4))
    assert default[0].description.startswith("Falling")
    assert lowered[0].description.startswith("Rising")


def test_entropy_only_scan_returns_entropy_module(tmp_path: Path) -> None:
    target = tmp_path / "mixed.bin"
    target.write_bytes(bytes(2048) + bytes(range(256)) * 8)
    modules = binwalk.scan(str(target), entropy=True, block=1024)
    assert [module.name for module in modules] == ["Entropy"]
    entropies = [round(result.entropy or 0.0, 6) for result in modules[0]]
    assert entropies == [0.0, 0.0, 1.0, 1.0]
    first = modules[0].results[2]
    assert first.entropy_bits == pytest.approx(8.0)
    assert first.module == "entropy"
    assert first.file == str(target)


@pytest.mark.usefixtures("backend")
def test_signature_and_entropy_return_both_modules() -> None:
    path = str(FIXTURES / "multi_signatures.bin")
    modules = binwalk.scan(path, signature=True, entropy=True)
    assert [module.name for module in modules] == ["Signature", "Entropy"]
    assert modules[0].errors == []
    assert [result.offset for result in modules[0]] == [0, 638, 1276]
    assert all(result.module == "entropy" for result in modules[1])


def test_fast_uses_zlib(tmp_path: Path) -> None:
    target = tmp_path / "text.bin"
    data = b"the quick brown fox " * 100
    target.write_bytes(data)
    (module,) = binwalk.scan(str(target), "-E", "-F", "-K", str(len(data)))
    assert module.results[0].entropy == pytest.approx(len(zlib.compress(data, 9)) / len(data))


def test_save_plot_writes_png(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    target = tmp_path / "plot me.bin"
    target.write_bytes(bytes(4096) + _random_bytes(4096, 4))
    (module,) = binwalk.scan(
        str(target), entropy=True, save=True, plot_directory=str(tmp_path / "plots")
    )
    expected = tmp_path / "plots" / "plot me.bin.png"
    assert module.plot == str(expected)
    assert expected.read_bytes()[:8] == PNG_MAGIC


def _png_width(path: str | None) -> int:
    assert path is not None
    header = Path(path).read_bytes()[:24]
    assert header[:8] == PNG_MAGIC
    return int.from_bytes(header[16:20], "big")


@pytest.mark.usefixtures("backend")
def test_plot_legend_lists_signatures_unless_disabled(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    path = str(FIXTURES / "multi_signatures.bin")
    with_legend = binwalk.scan(
        path, signature=True, entropy=True, save=True, plot_directory=str(tmp_path / "legend")
    )[1]
    without_legend = binwalk.scan(
        path,
        signature=True,
        entropy=True,
        save=True,
        nlegend=True,
        plot_directory=str(tmp_path / "plain"),
    )[1]
    assert with_legend.name == without_legend.name == "Entropy"
    assert _png_width(with_legend.plot) > _png_width(without_legend.plot)
