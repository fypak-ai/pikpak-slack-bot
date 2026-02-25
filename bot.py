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
URL_RE = re.compile(r"https?://[^\s>]+", re.IGNORECASE)
ED2K_RE = re.compile(r"ed2k://[^\s>]+", re.IGNORECASE)


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

    channel = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]

    await say(
        text=f":arrows_counterclockwise: Recebi {len(links)} link(s). Acionando PikPak...",
        channel=channel,
        thread_ts=thread_ts,
    )

    results = []
    for link in links:
        try:
            task = await pikpak.offline_download(link)
            file_id = task.get("id", "")
            name = task.get("name", link[:60])
            results.append({"name": name, "file_id": file_id, "status": "ok", "link": link})
        except Exception as exc:
            results.append({"name": link[:60], "file_id": "", "status": "error", "error": str(exc), "link": link})

    # Monta resposta consolidada
    lines = []
    for r in results:
        if r["status"] == "ok":
            share_url = await pikpak.get_share_link(r["file_id"]) if r["file_id"] else ""
            if share_url:
                lines.append(f":white_check_mark: *{r['name']}*\n{share_url}")
            else:
                lines.append(f":hourglass_flowing_sand: *{r['name']}* — download offline iniciado no PikPak.")
        else:
            lines.append(f":x: *{r['name']}* — erro: {r.get('error', 'desconhecido')}")

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
