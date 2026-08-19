from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)

    @property
    def lidl_session_file(self) -> Path:
        return self.project_root / "lidl_session.json"

    @property
    def kaufland_session_file(self) -> Path:
        return self.project_root / "kaufland_session.json"

    @property
    def db_file(self) -> Path:
        return self.project_root / "coupons.db"
