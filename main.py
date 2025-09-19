from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import urllib.parse
from typing import Optional

# Reuse existing logic from the scripts module
try:
    from src.scripts.youtube_downloader import get_video_info, get_direct_download_url
except Exception as e:
    # If import fails at runtime on some platforms, raise a clear error
    raise RuntimeError(
        "Failed to import youtube_downloader module from scripts/. Ensure the project root is on PYTHONPATH."
    ) from e

app = FastAPI(title="YouTube Downloader Backend", version="1.0.0")

# Configure CORS - adjust allowed origins for production as needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with specific frontend domain(s)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/video-info")
async def video_info(request: Request):
    try:
        payload = await request.json()
        url = payload.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        result = get_video_info(url)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch video information"))
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/download")
async def download(request: Request):
    try:
        payload = await request.json()
        url: Optional[str] = payload.get("url")
        quality: Optional[str] = payload.get("quality")
        fmt: str = payload.get("format") or "mp4"

        if not url or not quality:
            raise HTTPException(status_code=400, detail="URL and quality are required")

        result = get_direct_download_url(url, quality, fmt)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get download URL"))

        # Build absolute proxy URL for forced download via this backend
        base_url = str(request.base_url)
        direct_url = result["downloadUrl"]
        filename = result.get("filename") or "video.mp4"
        proxy_url = (
            f"{base_url}proxy-download?url="
            f"{urllib.parse.quote(direct_url, safe='')}"
            f"&filename={urllib.parse.quote(filename, safe='')}"
        )

        return JSONResponse({
            "success": True,
            "downloadUrl": proxy_url,
            "filename": filename,
            "title": result.get("title"),
            "message": "Download URL generated successfully",
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/proxy-download")
async def proxy_download(request: Request):
    try:
        params = request.query_params
        download_url = params.get("url")
        filename = params.get("filename")

        if not download_url or not filename:
            raise HTTPException(status_code=400, detail="URL and filename are required")

        # Forward Range header for partial content support
        range_header = request.headers.get("range")

        headers = {
            # Some CDNs require a browser-like UA and referer
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://www.youtube.com/",
        }
        if range_header:
            headers["Range"] = range_header

        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
            upstream = await client.stream("GET", download_url, headers=headers)

            # Validate upstream response
            if upstream.status_code not in (200, 206):
                # Drain response before closing to avoid warnings
                await upstream.aclose()
                raise HTTPException(status_code=502, detail=f"Upstream fetch failed: {upstream.status_code}")

            # Determine content type
            content_type = upstream.headers.get("content-type", "application/octet-stream")

            # Streaming generator
            async def iter_bytes():
                async for chunk in upstream.aiter_bytes():
                    yield chunk
                await upstream.aclose()

            response = StreamingResponse(iter_bytes(), status_code=upstream.status_code, media_type=content_type)
            # Propagate length if present for browsers' progress UI
            content_length = upstream.headers.get("content-length")
            if content_length:
                response.headers["Content-Length"] = content_length

            # Force download
            response.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
            response.headers["Cache-Control"] = "no-store"

            # Forward ranged response headers when present
            for header_name in ("Accept-Ranges", "Content-Range"):
                if header_name in upstream.headers:
                    response.headers[header_name] = upstream.headers[header_name]

            return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Optional local run helper
if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
