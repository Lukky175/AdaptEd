import yt_dlp

def get_playlist_videos(playlist_url):
    """
    Fetch video information from a YouTube playlist
    Returns a list of dictionaries with video title, id, and url
    """
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,  # Only get metadata, not full video info
        'force_generic_extractor': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        
        playlist_title = info.get('title', 'Playlist')
        videos = []
        
        for entry in info['entries']:
            video_id = entry['id']
            video_title = entry['title']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            videos.append({
                'id': video_id,
                'title': video_title,
                'url': video_url
            })
        
        return {
            'title': playlist_title,
            'videos': videos
        }

# Course playlist URLs
COURSE_PLAYLISTS = {
    'trigonometry': 'https://www.youtube.com/playlist?list=PLD6DA74C1DBF770E7',
    'sets': 'https://www.youtube.com/playlist?list=PLF7C-DWw7CnPJxHqSY0a-fun-4t_LpGVc',
    'calculus': 'https://www.youtube.com/playlist?list=PL19E79A0638C8D449',
    'polynomials': 'https://www.youtube.com/playlist?list=PLSQl0a2vh4HA5y-zmEVuu5WX84Tj-dRTw',
    'number_system': 'https://www.youtube.com/playlist?list=PL7eKoJuwryW7LLS4DIUpAC8WwdF2Fn0Jj',
    'probability': 'https://www.youtube.com/playlist?list=PLC58778F28211FA19'
}
