"""Pin the installed schwabdev DISTRIBUTION version (Note A: schwabdev.__version__
reads '3.0.4' inside the 3.0.5 dist -- assert the distribution metadata, not __version__)."""
import importlib.metadata as md

from packaging.version import Version


def test_schwabdev_distribution_in_v3_floored_range() -> None:
    v = Version(md.version("schwabdev"))
    # Pre-fix path: installed 2.5.1 -> Version("2.5.1") -> FAILS the >=3.0.5 bound.
    # Post-fix path: installed 3.0.5 -> Version("3.0.5") -> passes both bounds.
    assert Version("3.0.5") <= v < Version("4.0.0"), (
        f"schwabdev distribution {v} outside the OQ-3 floored range [3.0.5, 4.0.0); "
        "re-pin pyproject.toml and `pip install -e \".[dev,web]\"`."
    )


def test_pin_test_reads_distribution_metadata_not_dunder() -> None:
    # Discriminating source-level guard (Codex R1 minor; replaces the old `or True`
    # tautology): assert the pin test reads importlib.metadata.version, NOT
    # schwabdev.__version__ (which reads 3.0.4 in the 3.0.5 dist -- Note A). This is
    # robust to a future patch that fixes __version__.
    import inspect
    src = inspect.getsource(test_schwabdev_distribution_in_v3_floored_range)
    assert "md.version(" in src and "__version__" not in src
