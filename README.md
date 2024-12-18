# because quick access via YT is handy

Give it some folders for video, folder for Jams, put an ice pack on the computer and take a nap.

<iframe width="960" height="543" src="https://www.youtube.com/embed/DAsZSAEKRyw" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

# running it

`python3 -m venv env`

`source env/bin/activate`

`pip install -r requirements.txt`

`./process_media.sh -a 'wav,mp3,WAV,MP3' -v 'AVI,mp4,MOV,MP4' -w 1920 -h 1080 -d "/Volumes/Backups/media/video-to-process,/Volumes/Backups/icloud" "/Volumes/Backups/media/Jams/2.0GB SD/MUSIC/long" "/Users/selie/Documents/Projects/lilb-music-videos" -t "/Volumes/Backups/media/_temp"`
