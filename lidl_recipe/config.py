import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv, set_key

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    access_token: str = ""
    gemini_api_key: str = ""
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)

    @property
    def _env_path(self) -> Path:
        return self.project_root / ".env"

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv(_PROJECT_ROOT / ".env")
        return cls(
            access_token=os.getenv("LIDL_ACCESS_TOKEN", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        )

    def reload(self) -> None:
        load_dotenv(self._env_path, override=True)
        self.access_token = os.getenv("LIDL_ACCESS_TOKEN", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

    def require_access_token(self) -> str:
        if not self.access_token:
            print("No LIDL_ACCESS_TOKEN found in .env")
            print("Run: uv run lidl-recipe --login")
            sys.exit(1)
        return self.access_token

    def require_gemini_key(self) -> str:
        if not self.gemini_api_key:
            print("No GEMINI_API_KEY found in .env")
            print("Get a free key at https://aistudio.google.com/apikey")
            sys.exit(1)
        return self.gemini_api_key

    def save_token(self, token: str) -> None:
        if not self._env_path.exists():
            self._env_path.touch()
        set_key(str(self._env_path), "LIDL_ACCESS_TOKEN", token)

    @property
    def tasks_token_file(self) -> Path:
        return self.project_root / "tasks_token.json"

    @property
    def tasks_credentials_file(self) -> Path:
        return self.project_root / "credentials.json"
