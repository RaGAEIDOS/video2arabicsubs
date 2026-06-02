import os
import shutil
import whisper

_model = None
_model_name = None

# Ensure ffmpeg.exe is findable by whisper
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()  # full path like .../ffmpeg-win-x86_64-v7.1.exe
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)

    # Create a copy named ffmpeg.exe if it doesn't exist
    ffmpeg_link = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(ffmpeg_link):
        shutil.copy2(ffmpeg_exe, ffmpeg_link)

    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass


def load_model(model_size="small"):
    global _model, _model_name
    if _model is None or _model_name != model_size:
        _model = whisper.load_model(model_size)
        _model_name = model_size
    return _model


def transcribe(audio_path, model_size="small"):
    model = load_model(model_size)
    result = model.transcribe(audio_path, language="en")
    return result["segments"]
