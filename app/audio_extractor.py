import os
from moviepy import VideoFileClip


def extract_audio(video_path, output_dir=None):
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    if output_dir:
        audio_path = os.path.join(output_dir, f"{video_name}.wav")
    else:
        audio_path = f"{video_name}.wav"

    with VideoFileClip(video_path) as video:
        video.audio.write_audiofile(audio_path, codec='pcm_s16le', logger=None)

    return audio_path
