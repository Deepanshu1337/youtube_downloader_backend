import yt_dlp

def get_video_info(url):
    """Extract YouTube video metadata."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [
                {
                    'format_id': fmt['format_id'],
                    'ext': fmt['ext'],
                    'resolution': fmt.get('format_note', fmt.get('height', '')),
                    'filesize': fmt.get('filesize'),
                }
                for fmt in info.get('formats', [])
                if fmt.get('vcodec', 'none') != 'none' and fmt.get('acodec', 'none') != 'none'
            ]
            return {
                'success': True,
                'title': info['title'],
                'formats': formats,
                'thumbnail': info.get('thumbnail')
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_direct_download_url(url, quality, fmt='mp4'):
    """Get direct download URL for a given quality/format."""
    try:
        ydl_opts = {
            'quiet': True,
            'format': f'{quality}+bestaudio/best',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            selected_format = next((f for f in info['formats'] if f['format_id'] == quality), None)
            if not selected_format:
                return {'success': False, 'error': 'Requested quality not available'}
            download_url = selected_format['url']
            filename = ydl.prepare_filename(info)
            return {
                'success': True,
                'downloadUrl': download_url,
                'filename': filename,
                'title': info.get('title'),
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}
