"""Put the voice-over on the exported film: the film's music stays, ducked under the voice.

  .venv/bin/python -I outputs/video/mix_final.py <exported.mp4> [out.mp4] [--no-music]

The picture is copied untouched; the voice starts at 0 s, exactly where vo_timing.json placed each line.
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                check=True, capture_output=True, text=True).stdout)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    src = Path(args[0]); out = Path(args[1]) if len(args) > 1 else HERE / "Disha_How_a_Call_Works_with_voice.mp4"
    vo = HERE / "voiceover.wav"
    film, voice = dur(src), dur(vo)
    print(f"film {film:.1f}s · voice-over {voice:.1f}s")
    if abs(film - voice) > 1.0:
        print("WARNING: lengths differ by more than 1 s; the film may have been exported at another length")
    has_audio = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(src)],
                                    capture_output=True, text=True).stdout.strip())
    if "--no-music" in sys.argv or not has_audio:
        fc = "[1:a]volume=1.0,apad[mix]"
    else:
        # music at 55 %, pushed down a further ~12 dB whenever the voice speaks; voice slightly lifted
        fc = ("[1:a]asplit=2[v1][v2];"
              "[0:a]volume=0.55[m];[m][v1]sidechaincompress=threshold=0.02:ratio=10:attack=40:release=450[duck];"
              "[duck][v2]amix=inputs=2:normalize=0:weights=1 1.15,alimiter=limit=0.95[mix]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-i", str(vo), "-filter_complex", fc,
                    "-map", "0:v", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)
    print(f"wrote {out} ({dur(out):.1f}s)")

if __name__ == "__main__":
    main()
