import yt_dlp
import json
import sys
import os
from pathlib import Path

def get_video_info(url):
    """Extract video information without downloading"""
    print(f"[DEBUG] Getting info for URL: {url}", file=sys.stderr)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("[DEBUG] Extracting video info...", file=sys.stderr)
            info = ydl.extract_info(url, download=False)
            print(f"[DEBUG] Video info extracted successfully", file=sys.stderr)

            # Extract available formats
            formats = []
            if 'formats' in info:
                seen_qualities = set()
                for fmt in info['formats']:
                    if fmt.get('vcodec') != 'none' and fmt.get('height'):
                        quality = f"{fmt['height']}p"
                        if quality not in seen_qualities:
                            formats.append({
                                'quality': quality,
                                'format': 'mp4',
                                'format_id': fmt['format_id'],
                                'filesize': fmt.get('filesize', 0)
                            })
                            seen_qualities.add(quality)

                # Add audio-only option
                formats.append({
                    'quality': 'Audio Only',
                    'format': 'mp3',
                    'format_id': 'bestaudio',
                    'filesize': 0
                })

            # Format duration
            duration = info.get('duration', 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"

            # Format view count safely
            view_count = info.get('view_count', 0) or 0
            if view_count >= 1_000_000_000:
                views = f"{view_count / 1_000_000_000:.1f}B views"
            elif view_count >= 1_000_000:
                views = f"{view_count / 1_000_000:.1f}M views"
            elif view_count >= 1_000:
                views = f"{view_count / 1_000:.1f}K views"
            else:
                views = f"{view_count} views"

            result = {
                'success': True,
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': duration_str,
                'views': views,
                'channel': info.get('uploader', 'Unknown Channel'),
                'videoId': info.get('id', ''),
                'formats': formats,
                'is_live': info.get('is_live', False)
            }

            print(f"[DEBUG] Returning result: {result}", file=sys.stderr)
            return result

    except Exception as e:
        print(f"[DEBUG] Error in get_video_info: {str(e)}", file=sys.stderr)
        return {
            'success': False,
            'error': str(e)
        }

def get_direct_download_url(url, quality, format_type):
    """Get direct download URL without downloading the file"""
    try:
        print(f"[DEBUG] Getting direct download URL for: {url}", file=sys.stderr)

        # Configure options to get the direct URL
        if format_type == 'mp3':
            format_selector = 'bestaudio/best'
        else:
            if quality == '1080p':
                format_selector = 'best[height<=1080]'
            elif quality == '720p':
                format_selector = 'best[height<=720]'
            elif quality == '480p':
                format_selector = 'best[height<=480]'
            else:
                format_selector = 'best'

        ydl_opts = {
            'format': format_selector,
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')

            # Clean filename
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()

            # Get the direct download URL
            download_url = None
            if 'url' in info:
                download_url = info['url']
            elif 'formats' in info and info['formats']:
                for fmt in info['formats']:
                    if fmt.get('url'):
                        if format_type == 'mp3' and fmt.get('acodec') != 'none':
                            download_url = fmt['url']
                            break
                        elif format_type != 'mp3' and fmt.get('vcodec') != 'none':
                            if quality == '1080p' and fmt.get('height', 0) <= 1080:
                                download_url = fmt['url']
                                break
                            elif quality == '720p' and fmt.get('height', 0) <= 720:
                                download_url = fmt['url']
                                break
                            elif quality == '480p' and fmt.get('height', 0) <= 480:
                                download_url = fmt['url']
                                break

                if not download_url:
                    # Fallback
                    for fmt in info['formats']:
                        if fmt.get('url'):
                            download_url = fmt['url']
                            break

            if not download_url:
                raise Exception("No direct download URL found")

            file_ext = 'mp3' if format_type == 'mp3' else info.get('ext', 'mp4')

            return {
                'success': True,
                'downloadUrl': download_url,
                'filename': f"{safe_title}.{file_ext}",
                'title': title
            }

    except Exception as e:
        print(f"[DEBUG] Error getting direct URL: {str(e)}", file=sys.stderr)
        return {
            'success': False,
            'error': str(e)
        }

def download_video(url, quality, format_type, output_dir='downloads'):
    """Download video with specified quality and format"""
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"[DEBUG] Created/verified output directory: {output_path.absolute()}", file=sys.stderr)

        if format_type == 'mp3':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
            }
        else:
            if quality == '1080p':
                format_selector = 'best[height<=1080]'
            elif quality == '720p':
                format_selector = 'best[height<=720]'
            elif quality == '480p':
                format_selector = 'best[height<=480]'
            else:
                format_selector = 'best'

            ydl_opts = {
                'format': format_selector,
                'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()

            ydl.download([url])

            return {
                'success': True,
                'filename': f"{safe_title}.{format_type}",
                'title': title
            }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == "__main__":
    print(f"[DEBUG] Script started with args: {sys.argv}", file=sys.stderr)

    if len(sys.argv) < 2:
        result = {'success': False, 'error': 'No command provided'}
        print(json.dumps(result))
        sys.exit(1)

    command = sys.argv[1]
    print(f"[DEBUG] Command: {command}", file=sys.stderr)

    if command == 'info' and len(sys.argv) >= 3:
        url = sys.argv[2]
        print(f"[DEBUG] Processing info for URL: {url}", file=sys.stderr)
        result = get_video_info(url)
        print(json.dumps(result))
    elif command == 'get-url' and len(sys.argv) >= 5:
        url = sys.argv[2]
        quality = sys.argv[3]
        format_type = sys.argv[4]
        print(f"[DEBUG] Getting direct URL: {url}, {quality}, {format_type}", file=sys.stderr)
        result = get_direct_download_url(url, quality, format_type)
        print(json.dumps(result))
    elif command == 'download' and len(sys.argv) >= 5:
        url = sys.argv[2]
        quality = sys.argv[3]
        format_type = sys.argv[4]
        print(f"[DEBUG] Processing download: {url}, {quality}, {format_type}", file=sys.stderr)
        result = download_video(url, quality, format_type)
        print(json.dumps(result))
    else:
        result = {'success': False, 'error': 'Invalid command or arguments'}
        print(json.dumps(result))
