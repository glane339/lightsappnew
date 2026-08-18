"""Route dependencies. Everything long-lived hangs off ``app.state``."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from authoring.service import AuthoringService
from server.engine import ShowEngine
from storage.config import AppConfig
from storage.library import Library


def get_engine(request: Request) -> ShowEngine:
    return request.app.state.engine


def get_library(request: Request) -> Library:
    return request.app.state.library


def get_config(request: Request) -> AppConfig:
    return request.app.state.config


def get_authoring(request: Request) -> AuthoringService:
    return request.app.state.authoring


EngineDep = Annotated[ShowEngine, Depends(get_engine)]
LibraryDep = Annotated[Library, Depends(get_library)]
ConfigDep = Annotated[AppConfig, Depends(get_config)]
AuthoringDep = Annotated[AuthoringService, Depends(get_authoring)]
