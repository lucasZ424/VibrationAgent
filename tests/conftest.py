import os
import re
import shutil
import tempfile
from pathlib import Path

from _pytest.pathlib import make_numbered_dir
from _pytest.tmpdir import TempPathFactory

_SESSION_BASETEMP_ENV = "VIBRATION_AGENT_ACTIVE_PYTEST_BASETEMP"
_SESSION_CURRENT_LINK_ENV = "VIBRATION_AGENT_ACTIVE_PYTEST_CURRENT_LINK"


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _pytest_tmp_root() -> Path:
    root = _workspace_root() / "data" / "exports" / ".pytest_tmp_safe"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_rm(path: Path) -> None:
    root = Path(os.path.abspath(str(_workspace_root() / "data" / "exports" / ".pytest_tmp_safe")))
    target = Path(os.path.abspath(str(path)))
    if target == root or root not in target.parents:
        raise RuntimeError(f"Refusing to remove pytest temp path outside safe temp root: {target}")
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(target, ignore_errors=True)


def _clear_safe_tmp_root() -> None:
    root = _pytest_tmp_root()
    for child in root.iterdir():
        _safe_rm(child)


def _safe_name(value: Path | None) -> str:
    if value is None:
        return "default"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))[-80:] or "basetemp"


def _sandbox_getbasetemp(self: TempPathFactory) -> Path:
    if self._basetemp is not None:
        return self._basetemp

    root = _pytest_tmp_root()
    prefix = f"va-pytest-{os.getpid()}-{_safe_name(self._given_basetemp)}-"
    basetemp = make_numbered_dir(root=root, prefix=prefix, mode=0o777).resolve()
    self._basetemp = basetemp
    os.environ[_SESSION_BASETEMP_ENV] = str(basetemp)
    os.environ[_SESSION_CURRENT_LINK_ENV] = str(root / f"{prefix}current")
    self._trace("new sandbox basetemp", basetemp)
    return basetemp


def _sandbox_mktemp(self: TempPathFactory, basename: str, numbered: bool = True) -> Path:
    basename = self._ensure_relative_to_basetemp(basename)
    if numbered:
        path = make_numbered_dir(root=self.getbasetemp(), prefix=basename, mode=0o777)
    else:
        path = self.getbasetemp() / basename
        path.mkdir()
    self._trace("mktemp", path)
    return path


TempPathFactory.getbasetemp = _sandbox_getbasetemp
TempPathFactory.mktemp = _sandbox_mktemp


def pytest_configure(config):
    os.environ["VIBRATION_AGENT_PYTEST"] = "1"
    _clear_safe_tmp_root()
    safe_root = _pytest_tmp_root()
    os.environ["TMP"] = str(safe_root)
    os.environ["TEMP"] = str(safe_root)
    os.environ["TMPDIR"] = str(safe_root)
    tempfile.tempdir = str(safe_root)


def pytest_sessionfinish(session, exitstatus):
    current_link = os.environ.pop(_SESSION_CURRENT_LINK_ENV, "")
    if current_link:
        _safe_rm(Path(current_link))
    basetemp = os.environ.pop(_SESSION_BASETEMP_ENV, "")
    if basetemp:
        _safe_rm(Path(basetemp))
