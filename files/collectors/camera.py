
"""
CCTV camera status monitor.
Reports only camera name, UP/DOWN status, resolution, and FPS.
Reads camera RTSP URLs from cameras.json.
"""

import json
import subprocess
from pathlib import Path

CAMERA_FILE = Path("/var/lib/camera-discovery/cameras.json")


def _probe_camera(camera: dict) -> dict:
    name = camera.get("name") or camera.get("id") or "Unknown Camera"
    rtsp_data = camera.get("rtsp")
    if isinstance(rtsp_data, dict):
        rtsp_url = rtsp_data.get("url") if rtsp_data.get("valid") else None
    else:
        rtsp_url = camera.get("rtsp_url") or rtsp_data or camera.get("url")

    if not isinstance(rtsp_url, str):
        rtsp_url = None

    result = {
        "name": name,
        "status": "DOWN",
        "resolution": None,
        "fps": None,
    }

    if not rtsp_url:
        return result

    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-rtsp_transport", "tcp",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate",
                "-of", "json",
                rtsp_url,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if probe.returncode != 0:
            return result

        data = json.loads(probe.stdout)
        streams = data.get("streams", [])

        if not streams:
            return result

        stream = streams[0]
        result["status"] = "UP"

        width = stream.get("width")
        height = stream.get("height")

        if width and height:
            result["resolution"] = f"{width}x{height}"

        # Prefer average FPS; fall back to nominal FPS.
        for key in ("avg_frame_rate", "r_frame_rate"):
            value = stream.get(key)

            if value and value != "0/0":
                try:
                    numerator, denominator = map(int, value.split("/"))
                    if denominator:
                        result["fps"] = str(round(numerator / denominator, 2))
                        break
                except (ValueError, ZeroDivisionError):
                    continue

    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        pass

    return result


def collect() -> list[dict]:
    try:
        data = json.loads(CAMERA_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return []

    cameras = data.get("cameras", []) if isinstance(data, dict) else []

    return [_probe_camera(camera) for camera in cameras]


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
