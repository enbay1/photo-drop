# Photo Drop

Send photos from your phone to your PC over your home Wi-Fi: scan a QR code, pick photos, and they land in a folder on your disk. No app, no cloud, no cable.

I built it to get iPhone photos into [Meshroom](https://github.com/alicevision/Meshroom) for photogrammetry, but it works for any photos or videos from any phone with a browser.

- **One Python file, standard library only.** Nothing to `pip install`.
- **Scan to connect.** On startup the PC opens a page with a QR code; point your phone camera at it.
- **One folder per photo set.** Name each set (for example `clip-scan-1`) and it gets its own subfolder.
- **Duplicates are skipped.** Files with identical content to one already in the set are ignored, so re-sending is harmless.
- **Originals preserved.** Files are stored byte-for-byte with their original file date. Name clashes become `name (2).jpg`; nothing is overwritten.

## Requirements

- Python 3.9 or newer on the PC
- Phone and PC on the same network

## Usage

```bash
python server.py
```

On Windows you can double-click `start.bat` instead.

The server prints the phone link, opens the QR code page in your browser, and saves uploads to `uploads/` next to `server.py`.

On your phone:

1. Scan the QR code and open the link. Bookmark it; it stays the same between runs.
2. Enter a photo set name.
3. Tap **Choose photos** and select your photos.

On iPhone, photos picked from the library are sent as JPEG (iOS converts HEIC automatically).

### Options

| Option | Default | Description |
|---|---|---|
| `--dest FOLDER` | `./uploads` | Where photo sets are saved |
| `--port N` | `8765` | Port to listen on |
| `--token TOKEN` | from `--token-file` | Access token to use |
| `--token-file PATH` | `./.photodrop-token` | File holding the token; created with a random token on first run |
| `--no-browser` | off | Don't open the QR code page on startup |

To change the token (which invalidates old links), delete `.photodrop-token` and restart.

If Windows Firewall asks whether Python may communicate on the network, allow it on **private** networks.

## Security

Photo Drop is meant for short sessions on a network you trust, such as your home Wi-Fi. Please read this before using it.

**What protects it**

- Every request needs a random 72-bit access token, generated with Python's `secrets` module and compared in constant time.
- The server can only receive files. There is no way to list, download, or delete files through it.
- File and folder names from the phone are reduced to a single safe name, so uploads cannot escape the destination folder.
- The QR code page shows the token, so it is only served to requests from the PC itself (`127.0.0.1`).

**Limitations**

- **Plain HTTP.** Photos and the token are not encrypted in transit. Don't use it on shared or public Wi-Fi.
- **No upload quota.** Anyone with the token can upload files of up to 4 GB each until the disk is full.
- **QR page and DNS rebinding.** The QR page only checks the connection's source address, not the `Host` header, so a malicious website open in the PC's browser could in principle read the token through DNS rebinding.
- **Python's `http.server`** only implements basic security checks and is not intended for production use.
- The token is stored in plain text in `.photodrop-token` and in your phone's bookmarks.

Stop the server (Ctrl+C or close its window) when you're done uploading.

## How it works

The phone page (`index.html`) uploads each file as the raw body of a `POST /upload` request, two at a time, with the set name and file name in the query string and the token in an `X-Token` header. The server (`server.py`) streams each body to a temporary file while hashing it, then either discards it as a duplicate or moves it into place.

## License

[MIT](LICENSE). The bundled QR code library is [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) by Kazuhiko Arase, also MIT; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
