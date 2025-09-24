import os
from pathlib import Path
import tempfile
from tempfile import _TemporaryFileWrapper
from typing import Any


class TempNoteFile:
    def __init__(
        self,
        suffix: str = ".md",
        encoding: str = "utf-8",
        dir: Path | None = None,
        source_path: Path | None = None,
    ) -> None:
        self.encoding: str = encoding
        self.suffix: str = suffix
        self.dir: Path = dir or Path("/tmp/brainops")
        self.source_path: Path | None = source_path
        self._tmp_file: _TemporaryFileWrapper[str] | None = None
        self.tmp_path: Path | None = None

        self.dir.mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> "TempNoteFile":
        tmp = tempfile.NamedTemporaryFile(
            mode="w+", encoding=self.encoding, delete=False, suffix=self.suffix, dir=str(self.dir)
        )
        self._tmp_file = tmp
        self.tmp_path = Path(tmp.name)

        if self.source_path:
            with self.source_path.open("r", encoding=self.encoding) as src:
                assert self._tmp_file is not None
                self._tmp_file.write(src.read())
                self._tmp_file.flush()
                os.fsync(self._tmp_file.fileno())

        return self

    def write_block(self, text: str) -> None:
        assert self._tmp_file is not None
        self._tmp_file.write(text)
        self._tmp_file.flush()
        os.fsync(self._tmp_file.fileno())

    def finalize(self, final_path: Path) -> Path:
        if self._tmp_file is None or self.tmp_path is None:
            raise RuntimeError("Impossible de finaliser : fichier non initialisé.")
        self._tmp_file.close()

        final_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(self.tmp_path, final_path)
        self.tmp_path = None
        return final_path

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any | None) -> None:
        if self._tmp_file and not self._tmp_file.closed:
            self._tmp_file.close()
        if self.tmp_path and self.tmp_path.exists():
            self.tmp_path.unlink(missing_ok=True)
