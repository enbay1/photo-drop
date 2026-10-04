"""
Photo Drop: a small LAN upload server. It sends photos from a phone to this PC.

To start:  python server.py [--dest FOLDER] [--port 8765]
The server opens a QR code page on the PC. Scan the QR code with the phone.
The phone and the PC must be on the same Wi-Fi network.

The server saves each upload "set" in a different subfolder of --dest. If a file
has the same content as a file in the set, the server does not save it. Thus,
you can upload a file again without risk.
The server uses only the standard library.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
MAX_FILE_BYTES = 4 * 1024 ** 3  # Maximum of 4 GB for each file (also for videos)
CHUNK = 1024 * 1024
SAFE_CHARS = re.compile(r"[^A-Za-z0-9._ ()\-]+")

_hashLock = threading.Lock()
_hashIndex = {}  # Set folder -> {SHA-256 hex digest: path of the file with this content}


def safeName(name, fallback):
    """Change a name from the client to one safe path component."""
    name = os.path.basename(name.replace("\\", "/")).strip()
    name = SAFE_CHARS.sub("_", name).strip(" .")
    return name[:120] or fallback


def fileHash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def knownHashes(setDir):
    """Return a map of content hash -> path for the files in a set folder. Calculate the map one time and keep it."""
    key = str(setDir)
    if key not in _hashIndex:
        # Ignore uploads that are not complete. This includes the upload that the server checks now.
        _hashIndex[key] = {fileHash(p): p for p in setDir.iterdir()
                           if p.is_file() and not p.name.startswith(".upload-")} if setDir.exists() else {}
    return _hashIndex[key]


def isDuplicate(hashes, digest):
    """Return True if a file with this content is on the disk. Remove the entries for files that were deleted."""
    existing = hashes.get(digest)
    if existing is None:
        return False
    if existing.is_file():
        return True
    del hashes[digest]
    return False


def uniquePath(folder, name):
    """Return folder/name. If a different file uses this name, add ' (2)', ' (3)', and so on."""
    candidate = folder / name
    stem, suffix = candidate.stem, candidate.suffix
    i = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({i}){suffix}"
        i += 1
    return candidate


def loadToken(tokenFile):
    """Read the access token from tokenFile. If there is no token, make a random token and save it."""
    if tokenFile.exists():
        token = tokenFile.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(9)
    tokenFile.write_text(token + "\n", encoding="utf-8")
    return token


def lanAddress():
    """Return the most probable LAN IP address of this PC. This function does not send packets."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "PhotoDrop/1.0"

    def log_message(self, fmt, *args):
        pass  # Show only upload messages in the console

    def sendJson(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, query):
        token = self.headers.get("X-Token") or query.get("t", [""])[0]
        return secrets.compare_digest(token, self.server.token)

    def isLocal(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def sendFile(self, name, contentType):
        data = (HERE / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", contentType)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        # The QR page shows the token. Thus, send it only to this PC.
        if url.path in ("/qr", "/qrinfo", "/qrcode.min.js"):
            if not self.isLocal():
                self.send_error(403, "The QR page is available only on the PC that runs Photo Drop.")
            elif url.path == "/qr":
                self.sendFile("qr.html", "text/html; charset=utf-8")
            elif url.path == "/qrcode.min.js":
                self.sendFile("qrcode.min.js", "application/javascript")
            else:
                self.sendJson(200, {"url": self.server.url, "dest": str(self.server.dest)})
            return
        if url.path == "/":
            if not self.authorized(query):
                self.send_error(403, "The token is missing or not correct. Use the full link that the server shows.")
                return
            page = (HERE / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page)
        elif url.path == "/info":
            if not self.authorized(query):
                self.sendJson(403, {"error": "forbidden"})
                return
            self.sendJson(200, {"dest": str(self.server.dest)})
        else:
            self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path != "/upload":
            self.send_error(404)
            return
        if not self.authorized(query):
            self.sendJson(403, {"error": "forbidden"})
            return

        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_FILE_BYTES:
            self.sendJson(411 if length < 0 else 413, {"error": "The Content-Length header is missing or not correct."})
            return
        if length == 0:
            # Sometimes iOS gives an empty file to the browser. Do not save empty files.
            self.sendJson(400, {"error": "The file is empty. Send the file again."})
            return
        expected = self.headers.get("X-File-Size")
        if expected and expected.isdigit() and int(expected) != length:
            self.sendJson(400, {"error": f"The upload is not complete ({length} of {expected} bytes). Send the file again."})
            return

        setName = safeName(query.get("set", [""])[0], "untitled")
        fileName = safeName(query.get("name", [""])[0], "photo.jpg")
        setDir = self.server.dest / setName
        setDir.mkdir(parents=True, exist_ok=True)

        # Write the body to a temporary file in the same folder. Calculate the hash at the same time.
        h = hashlib.sha256()
        remaining = length
        fd, tmpName = tempfile.mkstemp(dir=setDir, prefix=".upload-", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as out:
                while remaining > 0:
                    block = self.rfile.read(min(CHUNK, remaining))
                    if not block:
                        raise ConnectionError("The client disconnected.")
                    out.write(block)
                    h.update(block)
                    remaining -= len(block)
            digest = h.hexdigest()

            with _hashLock:
                hashes = knownHashes(setDir)
                if isDuplicate(hashes, digest):
                    os.remove(tmpName)
                    print(f"  skip  {setName}/{fileName} (same content as {hashes[digest].name})")
                    self.sendJson(200, {"status": "duplicate", "name": fileName, "of": hashes[digest].name})
                    return
                final = uniquePath(setDir, fileName)
                os.replace(tmpName, final)
                hashes[digest] = final

            # If the browser sends the original timestamp of the photo, keep it
            lastModified = self.headers.get("X-Last-Modified")
            if lastModified and lastModified.isdigit():
                ts = int(lastModified) / 1000
                os.utime(final, (ts, ts))

            print(f"  saved {setName}/{final.name} ({length / 1e6:.1f} MB)")
            self.sendJson(200, {"status": "saved", "name": final.name, "path": str(final)})
        except Exception as exc:
            if os.path.exists(tmpName):
                os.remove(tmpName)
            print(f"  FAIL  {setName}/{fileName}: {exc}")
            try:
                self.sendJson(500, {"error": str(exc)})
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description="LAN photo upload server")
    parser.add_argument("--dest", default=str(HERE / "uploads"), help="the folder for the photo sets")
    parser.add_argument("--port", type=int, default=8765, help="the port for the server")
    parser.add_argument("--token", default=None, help="the access token (default: the token in --token-file)")
    parser.add_argument("--token-file", default=str(HERE / ".photodrop-token"),
                        help="the file that contains the access token. If the file does not exist, the server makes it with a random token.")
    parser.add_argument("--no-browser", action="store_true", help="do not open the QR code page when the server starts")
    args = parser.parse_args()

    dest = Path(args.dest).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.dest = dest
    server.token = args.token or loadToken(Path(args.token_file).expanduser())

    url = f"http://{lanAddress()}:{args.port}/?t={server.token}"
    server.url = url
    qrPage = f"http://127.0.0.1:{args.port}/qr"
    print("Photo Drop started.")
    print(f"  Link for the phone (same Wi-Fi network): {url}")
    print(f"  QR code page: {qrPage}")
    print(f"  Save folder: {dest}")
    print("  To stop the server, push Ctrl+C.\n", flush=True)
    if not args.no_browser:
        webbrowser.open(qrPage)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
