"""Wrapper sobre a biblioteca pikpakapi para offline download e share links.

Usa pikpakapi (pip install pikpakapi) que lida com captcha token, device ID
e demais headers exigidos pela API PikPak de forma automática.
"""

from typing import Optional
from pikpakapi import PikPakApi


class PikPakClient:
    def __init__(self, username: str, password: str, offline_path: str = ""):
        self.offline_path = offline_path.strip() or None
        self._api = PikPakApi(username=username, password=password)

    async def login(self):
        """Autentica no PikPak (lida com captcha automaticamente)."""
        await self._api.login()

    async def offline_download(self, url: str) -> dict:
        """Aciona download offline de um magnet/URL e retorna o task dict."""
        parent_id = await self._resolve_path() if self.offline_path else None
        result = await self._api.offline_download(url, parent_id=parent_id or "")
        # pikpakapi retorna dict com 'task' ou 'file' dependendo da versão
        if isinstance(result, dict):
            return result.get("task") or result.get("file") or result
        return {"name": url[:60], "id": ""}

    async def get_share_link(self, file_id: str) -> Optional[str]:
        """Gera um share link público. Retorna None se não disponível."""
        try:
            result = await self._api.get_share_list()
            # Tenta criar share para o file_id específico
            share = await self._api.create_share(
                file_ids=[file_id],
                share_to="publiclink",
                expiration_days=-1,
                pass_code_option="NOT_REQUIRED",
            )
            if isinstance(share, dict):
                return share.get("share_url") or share.get("share_link")
        except Exception:
            pass
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
            try:
                files_data = await self._api.file_list(parent_id=parent_id)
                files = files_data.get("files", []) if isinstance(files_data, dict) else []
                folders = {
                    f["name"]: f["id"]
                    for f in files
                    if f.get("kind") == "drive#folder" and not f.get("trashed")
                }
                if part in folders:
                    parent_id = folders[part]
                else:
                    created = await self._api.create_folder(name=part, parent_id=parent_id)
                    parent_id = created.get("file", {}).get("id", "")
            except Exception:
                break
        return parent_id
