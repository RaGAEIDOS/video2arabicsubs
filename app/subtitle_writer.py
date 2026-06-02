import os


def write_srt(segments, translated_texts, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, (seg, trans) in enumerate(zip(segments, translated_texts), 1):
            start = _format_time(seg['start'])
            end = _format_time(seg['end'])
            f.write(f"{i}\n{start} --> {end}\n{trans}\n\n")


def _format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
