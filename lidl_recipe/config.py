import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv, set_key

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID_RECIPE_PROVIDERS = ("gemini", "ollama")
DEFAULT_OLLAMA_URL = "http://localhost:11434"


@dataclass
class Config:
    access_token: str = ""
    gemini_api_key: str = ""
    recipe_provider: str = "gemini"
    ollama_url: str = DEFAULT_OLLAMA_URL
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)

    @property
    def _env_path(self) -> Path:
        return self.project_root / ".env"

    def _load(self) -> None:
        self.access_token = os.getenv("LIDL_ACCESS_TOKEN", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.recipe_provider = os.getenv("RECIPE_PROVIDER", "gemini").strip().lower() or "gemini"
        self.ollama_url = os.getenv("OLLAMA_URL", "") or DEFAULT_OLLAMA_URL

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv(_PROJECT_ROOT / ".env")
        cfg = cls()
        cfg._load()
        return cfg

    def reload(self) -> None:
        load_dotenv(self._env_path, override=True)
        self._load()

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

    def require_recipe_provider(self) -> str:
        if self.recipe_provider not in VALID_RECIPE_PROVIDERS:
            print(f"Invalid RECIPE_PROVIDER: {self.recipe_provider!r} (use 'gemini' or 'ollama')")
            sys.exit(1)
        return self.recipe_provider

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

    @property
    def lidl_session_file(self) -> Path:
        return self.project_root / "lidl_session.json"

    @property
    def db_file(self) -> Path:
        return self.project_root / "coupons.db"
