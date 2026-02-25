"""PikPak Slack Bot — envia magnet/URL para download offline via PikPak e responde no canal."""

import os
import re
import asyncio
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from pikpak_client import PikPakClient

load_dotenv()

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
pikpak = PikPakClient(
    username=os.environ["PIKPAK_USERNAME"],
    password=os.environ["PIKPAK_PASSWORD"],
    offline_path=os.environ.get("PIKPAK_OFFLINE_PATH", ""),
)

# Regex para detectar magnet links e URLs HTTP(S)
MAGNET_RE = re.compile(r"magnet:\?xt=urn:[a-zA-Z0-9]+:[a-zA-Z0-9]{32,}", re.IGNORECASE)
URL_RE    = re.compile(r"https?://[^\s>]+", re.IGNORECASE)
ED2K_RE   = re.compile(r"ed2k://[^\s>]+", re.IGNORECASE)


def extract_links(text: str) -> list[str]:
    """Extrai todos os magnet, ed2k e HTTP URLs de um texto."""
    links = []
    links += MAGNET_RE.findall(text)
    links += ED2K_RE.findall(text)
    # URLs HTTP apenas se não forem do Slack (evita links de mensagens)
    for url in URL_RE.findall(text):
        if not url.startswith("https://slack.com"):
            links.append(url)
    return links


@app.event("message")
async def handle_message(event, say, client):
    """Captura mensagens no canal e aciona downloads."""
    text = event.get("text", "")
    links = extract_links(text)

    if not links:
        return  # Mensagem normal, ignora

    channel   = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]

    # Confirmação imediata
    await say(
        text=f":arrows_counterclockwise: Recebi {len(links)} link(s). Acionando PikPak e aguardando download...",
        channel=channel,
        thread_ts=thread_ts,
    )

    results = []
    for link in links:
        try:
            task = await pikpak.offline_download(link)
            results.append({**task, "link": link})
        except Exception as exc:
            results.append({"name": link[:80], "file_id": "", "task_id": "", "status": "error", "error": str(exc), "link": link})

    # Monta resposta consolidada
    lines = []
    for r in results:
        name = r.get("name", r["link"][:80])
        status = r.get("status", "error")

        if status == "complete" and r.get("file_id"):
            share_url = await pikpak.get_share_link(r["file_id"])
            if share_url:
                lines.append(f":white_check_mark: *{name}*\n{share_url}")
            else:
                lines.append(f":hourglass_flowing_sand: *{name}* — download concluído no PikPak (share link indisponível).")
        elif status == "timeout":
            lines.append(f":hourglass: *{name}* — download iniciado, mas ainda processando no PikPak. Verifique sua conta em alguns minutos.")
        else:
            err = r.get("error", "desconhecido")
            lines.append(f":x: *{name}* — erro: {err}")

    await say(
        text="\n\n".join(lines),
        channel=channel,
        thread_ts=thread_ts,
    )


async def main():
    await pikpak.login()
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
