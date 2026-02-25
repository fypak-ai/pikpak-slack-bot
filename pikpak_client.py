"""Wrapper sobre a biblioteca pikpakapi para offline download e share links.

Usa pikpakapi (pip install pikpakapi) que lida com captcha token, device ID
e demais headers exigidos pela API PikPak de forma automática.

O offline_download retorna um TASK (não o arquivo imediato).
Esta classe faz polling até a task completar e retorna o file_id real.
"""

import asyncio
from typing import Optional
from pikpakapi import PikPakApi


POLL_INTERVAL = 5   # segundos entre cada verificação
POLL_TIMEOUT  = 300 # timeout máximo em segundos (5 min)


class PikPakClient:
    def __init__(self, username: str, password: str, offline_path: str = ""):
        self.offline_path = offline_path.strip() or None
        self._api = PikPakApi(username=username, password=password)

    async def login(self):
        """Autentica no PikPak (lida com captcha automaticamente)."""
        await self._api.login()

    # ------------------------------------------------------------------
    # Offline download com polling
    # ------------------------------------------------------------------

    async def offline_download(self, url: str) -> dict:
        """Aciona download offline e AGUARDA conclusão.

        Retorna dict com:
          - name      (str)  nome do arquivo
          - file_id   (str)  ID do arquivo no PikPak (após conclusão)
          - task_id   (str)  ID da task de download
          - status    (str)  'complete' | 'error' | 'timeout'
        """
        parent_id = await self._resolve_path() if self.offline_path else None

        result = await self._api.offline_download(url, parent_id=parent_id or "")

        # pikpakapi retorna dict com 'task' ou 'file' dependendo da versão
        if isinstance(result, dict):
            task = result.get("task") or result.get("file") or result
        else:
            task = {"name": url[:80], "id": ""}

        task_id  = task.get("id", "")
        name     = task.get("name", url[:80])
        file_id  = task.get("file_id", "")  # pode vir preenchido direto

        # Se já temos file_id, não precisamos de polling
        if file_id:
            return {"name": name, "file_id": file_id, "task_id": task_id, "status": "complete"}

        # Polling: aguarda task completar
        if task_id:
            file_id, name = await self._poll_task(task_id, name)
            if file_id:
                return {"name": name, "file_id": file_id, "task_id": task_id, "status": "complete"}

        # Fallback: retorna o que temos (sem file_id, share link ficará vazio)
        return {"name": name, "file_id": "", "task_id": task_id, "status": "timeout"}

    async def _poll_task(self, task_id: str, fallback_name: str) -> tuple[str, str]:
        """Faz polling na lista de tasks até a task_id completar.

        Retorna (file_id, name) quando concluída, ou ("", fallback_name) no timeout.
        """
        elapsed = 0
        while elapsed < POLL_TIMEOUT:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            try:
                tasks_data = await self._api.get_task_list()
                # pikpakapi retorna lista ou dict com 'tasks'
                if isinstance(tasks_data, dict):
                    tasks = tasks_data.get("tasks", [])
                elif isinstance(tasks_data, list):
                    tasks = tasks_data
                else:
                    continue

                for t in tasks:
                    if t.get("id") != task_id:
                        continue
                    phase  = t.get("phase", "").upper()    # PHASE_TYPE_COMPLETE etc.
                    status = t.get("status", "").upper()
                    fid    = t.get("file_id", "") or t.get("file", {}).get("id", "")
                    nm     = t.get("name", "") or t.get("file", {}).get("name", fallback_name)

                    # Concluído com sucesso
                    if "COMPLETE" in phase or "COMPLETE" in status:
                        return fid or "", nm or fallback_name

                    # Falhou
                    if "ERROR" in phase or "ERROR" in status or "FAIL" in phase:
                        return "", nm or fallback_name

            except Exception:
                pass  # ignora erros transitórios de rede

        return "", fallback_name

    # ------------------------------------------------------------------
    # Share link
    # ------------------------------------------------------------------

    async def get_share_link(self, file_id: str) -> Optional[str]:
        """Gera um share link público. Retorna None se não disponível."""
        try:
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

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

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
