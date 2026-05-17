from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import GithubClientConfig, GithubDevicePollRequest, GithubDeviceStartRequest
from services.auth_service import clear_github_auth, github_status, poll_device_flow, save_client_id, start_device_flow


router = APIRouter(prefix="/api/auth/github", tags=["auth"])


@router.get("/status")
def status():
    return github_status()


@router.post("/config")
def config(payload: GithubClientConfig):
    try:
        return save_client_id(payload.client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/device/start")
async def device_start(payload: GithubDeviceStartRequest):
    try:
        return await start_device_flow(payload.client_id, payload.scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/device/poll")
async def device_poll(payload: GithubDevicePollRequest):
    return await poll_device_flow(payload.session_id)


@router.post("/logout")
def logout():
    return clear_github_auth()
