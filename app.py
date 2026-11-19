import os, re, asyncio
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="AM Link Hunter")
app.mount("/static", StaticFiles(directory="static"), name="static")

class ScanRequest(BaseModel):
    url: HttpUrl

def valid_tiktok(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "tiktok.com" or host.endswith(".tiktok.com")

def extract_links(text: str):
    return [u.rstrip(".,!?;:)]}") for u in re.findall(r"https?://[^\s<>\"']+", text or "")]

@app.get("/")
async def home():
    return FileResponse("static/index.html")

@app.post("/api/scan")
async def scan(req: ScanRequest):
    url = str(req.url)
    if not valid_tiktok(url):
        raise HTTPException(400, "URL harus berasal dari TikTok.")
    token = os.getenv("TIKTOK_MS_TOKEN", "").strip()
    if not token:
        raise HTTPException(503, "Sesi TikTok belum disiapkan. Ikuti langkah TIKTOK_MS_TOKEN di README.")
    try:
        from TikTokApi import TikTokApi
        api = TikTokApi()
        await api.create_sessions(
            ms_tokens=[token],
            num_sessions=1,
            sleep_after=3,
            browser=os.getenv("TIKTOK_BROWSER", "chromium")
        )
        video = api.video(url=url)
        comments_scanned = 0
        results = []
        seen = set()
        async for comment in video.comments(count=int(os.getenv("MAX_COMMENTS", "500"))):
            comments_scanned += 1
            text = getattr(comment, "text", "") or ""
            for link in extract_links(text):
                if link in seen:
                    continue
                seen.add(link)
                preset = bool(re.search(r"\.(xml|am|zip)(?:$|[?#])|alight|motion|preset", link, re.I))
                results.append({"comment": text, "url": link, "is_preset": preset})
        await api.close_sessions()
        return {
            "comments_scanned": comments_scanned,
            "results": results,
            "message": f"Selesai memindai {comments_scanned} komentar. Ditemukan {len(results)} link."
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"TikTok gagal diakses: {type(exc).__name__}: {exc}")
