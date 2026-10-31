"""Telegram webhook API routes."""

from fastapi import APIRouter

router = APIRouter(prefix="/telegram", tags=["telegram"])
