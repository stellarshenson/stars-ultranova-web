"""
Application configuration.
"""
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration."""
    app_name: str = "Stars Nova Web"
    version: str = "0.1.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000


config = Config()
