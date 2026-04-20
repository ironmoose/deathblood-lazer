"""Deathblood Lazer development server — static files + skeleton editor API."""

import json
import re
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

CHARS_DIR = Path("assets/sprites/characters")


def find_east_image(frames_dir):
    """Find the best east-facing PNG, preferring the highest version number."""
    candidates = []
    for p in frames_dir.glob("*_east.png"):
        # Skip north-east, south-east variants
        if "north" in p.name or "south" in p.name:
            continue
        # Extract version number if present (e.g. _v8_east.png)
        m = re.search(r"_v(\d+)_east\.png$", p.name)
        version = int(m.group(1)) if m else 0
        candidates.append((version, p))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


_DIR_PATTERN = re.compile(
    r"cc_.*?(?:_v(\d+))?_(south-?west|south-?east|north-?west|north-?east|south|north|east|west)\.png$"
)

_NORMALIZE = {
    "southwest": "south-west",
    "southeast": "south-east",
    "northwest": "north-west",
    "northeast": "north-east",
}


def find_direction_images(frames_dir):
    """Return {direction: '/assets/.../file.png'} for the highest-version CC sprite per direction."""
    # best[(normalized_dir)] = (version, Path)
    best = {}
    for p in frames_dir.glob("cc_*.png"):
        m = _DIR_PATTERN.search(p.name)
        if not m:
            continue
        version = int(m.group(1)) if m.group(1) else 0
        raw_dir = m.group(2)
        direction = _NORMALIZE.get(raw_dir, raw_dir)
        prev = best.get(direction)
        if prev is None or version > prev[0]:
            best[direction] = (version, p)
    return {d: "/" + p.as_posix() for d, (_, p) in best.items()}


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    # ── API router ──────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/api/characters":
            return self._list_characters()
        m = re.match(r"^/api/characters/([^/]+)/skeleton$", self.path)
        if m:
            return self._get_skeleton(m.group(1))
        super().do_GET()

    def do_POST(self):
        m = re.match(r"^/api/characters/([^/]+)/skeleton$", self.path)
        if m:
            return self._save_skeleton(m.group(1))
        self._send_json({"error": "not found"}, 404)

    # ── Endpoints ───────────────────────────────────────────────
    def _list_characters(self):
        characters = []
        if not CHARS_DIR.is_dir():
            return self._send_json(characters)
        for d in sorted(CHARS_DIR.iterdir()):
            if not d.is_dir():
                continue
            frames = d / "frames"
            if not frames.is_dir():
                continue
            images = find_direction_images(frames)
            characters.append({
                "name": d.name,
                "images": images,
                "east_image": images.get("east"),
                "has_skeleton": (d / "skeleton.json").exists(),
            })
        self._send_json(characters)

    def _get_skeleton(self, name):
        path = CHARS_DIR / name / "skeleton.json"
        if not path.exists():
            return self._send_json({"error": "not found"}, 404)
        self._send_json(json.loads(path.read_text(encoding="utf-8")))

    def _save_skeleton(self, name):
        char_dir = CHARS_DIR / name
        if not char_dir.is_dir():
            return self._send_json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        (char_dir / "skeleton.json").write_text(
            json.dumps(body, indent=2) + "\n", encoding="utf-8"
        )
        self._send_json({"ok": True})

    # ── Helpers ─────────────────────────────────────────────────
    def _send_json(self, data, status=200):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        # Quieter than default — skip .import file noise
        if len(args) >= 1 and ".import" in str(args[0]):
            return
        super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    server = HTTPServer(("", port), Handler)
    print(f"Deathblood Lazer dev server running at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
