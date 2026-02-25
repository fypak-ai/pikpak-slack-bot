"""Cliente PikPak minimalista para offline download e geração de share links.

Baseado na API não-oficial do PikPak (compatível com PikPakAutoOfflineDownloadBot).
"""

import httpx
import asyncio
from typing import Optional


CLIENT_ID = "YNxT9w7GMdWvEOKa"
CLIENT_SECRET = "dbw2OtmVEeuUvIptb1Coyg"
API_BASE = "https://api-drive.mypikpak.com"
USER_BASE = "https://user.mypikpak.com"


class PikPakClient:
    def __init__(self, username: str, password: str, offline_path: str = ""):
        self.username = username
        self.password = password
        self.offline_path = offline_path.strip() or None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=30)

    async def login(self):
        """Autentica no PikPak e armazena tokens."""
        resp = await self._client.post(
            f"{USER_BASE}/v1/auth/signin",
            json={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": self.username,
                "password": self.password,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]

    async def _refresh(self):
        """Renova o access token usando o refresh token."""
        resp = await self._client.post(
            f"{USER_BASE}/v1/auth/token",
            json={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _post(self, url: str, json: dict, retry: bool = True) -> dict:
        resp = await self._client.post(url, json=json, headers=self._headers())
        if resp.status_code == 401 and retry:
            await self._refresh()
            return await self._post(url, json, retry=False)
        resp.raise_for_status()
        return resp.json()

    async def _get(self, url: str, params: dict = None, retry: bool = True) -> dict:
        resp = await self._client.get(url, params=params, headers=self._headers())
        if resp.status_code == 401 and retry:
            await self._refresh()
            return await self._get(url, params, retry=False)
        resp.raise_for_status()
        return resp.json()

    async def offline_download(self, url: str) -> dict:
        """Aciona download offline de um magnet/URL e retorna o task dict do PikPak."""
        parent_id = await self._resolve_path() if self.offline_path else ""
        payload = {
            "kind": "drive#file",
            "name": "",
            "upload_type": "UPLOAD_TYPE_URL",
            "url": {"url": url},
            "folder_type": "DOWNLOAD" if not parent_id else "",
        }
        if parent_id:
            payload["parent_id"] = parent_id

        data = await self._post(f"{API_BASE}/drive/v1/files", payload)
        return data.get("file", data)

    async def get_share_link(self, file_id: str) -> Optional[str]:
        """Gera um share link público para o arquivo. Retorna None se não disponível."""
        try:
            data = await self._post(
                f"{API_BASE}/drive/v1/share",
                {
                    "file_ids": [file_id],
                    "share_to": "publiclink",
                    "expiration_days": -1,
                    "pass_code_option": "NOT_REQUIRED",
                },
            )
            return data.get("share_url") or data.get("share_link")
        except Exception:
            return None

    async def _resolve_path(self) -> str:
        """Resolve um caminho como /downloads para o parent_id correspondente.
        Cria as pastas intermediárias se necessário.
        """
        parts = [p for p in (self.offline_path or "").split("/") if p]
        if not parts:
            return ""

        parent_id = ""
        for part in parts:
            data = await self._get(
                f"{API_BASE}/drive/v1/files",
                params={
                    "parent_id": parent_id,
                    "filters": '{"trashed":{"eq":false},"kind":{"eq":"drive#folder"}}',
                    "page_token": "",
                    "limit": 100,
                },
            )
            folders = {f["name"]: f["id"] for f in data.get("files", [])}
            if part in folders:
                parent_id = folders[part]
            else:
                created = await self._post(
                    f"{API_BASE}/drive/v1/files",
                    {"kind": "drive#folder", "name": part, "parent_id": parent_id},
                )
                parent_id = created["file"]["id"]
        return parent_id
