from pathlib import Path

from pydantic import BaseModel


class AppConfig(BaseModel):
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
