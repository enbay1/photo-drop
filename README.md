# Photo Drop

Photo Drop sends photos from your phone to your PC on your home Wi-Fi network. Scan a QR code and select the photos. The PC saves the photos in a folder on its disk. You do not need an app, a cloud service, or a cable.

Photo Drop was made to send iPhone photos to [Meshroom](https://github.com/alicevision/Meshroom) for photogrammetry. You can also use it for other photos and videos. It operates with all phones that have a web browser.

- **One Python file. Only the standard library.** You do not need to install packages with `pip`.
- **Scan a QR code to connect.** When the server starts, the PC opens a page that shows a QR code. Point the phone camera at the QR code.
- **One folder for each photo set.** Give a name to each set (for example, `clip-scan-1`). Photo Drop makes a subfolder for each set.
- **Photo Drop ignores duplicate files.** If a file has the same content as a file in the set, Photo Drop does not save it. Thus, you can send a file again without risk.
- **Photo Drop keeps the original files.** It saves each file without changes and keeps the original file date. If a file name is already in use, Photo Drop adds a number, for example `name (2).jpg`. It does not overwrite files.

## Requirements

- Python 3.9 or a later version on the PC
- The phone and the PC on the same network

## Usage

To start the server, type this command:

```bash
python server.py
```

On Windows, you can also double-click `start.bat`.

The server does these steps:

1. It shows the link for the phone.
2. It opens the QR code page in your browser.
3. It saves the uploads in the `uploads/` folder, adjacent to `server.py`.

On the phone, do these steps:

1. Scan the QR code.
2. Open the link.
3. Bookmark the link. The link does not change when you start the server again.
4. Type a name for the photo set.
5. Tap **Select photos**.
6. Select the photos.

On an iPhone, iOS changes HEIC photos from the photo library to JPEG automatically. Thus, Photo Drop receives JPEG files.

### Options

| Option | Default | Description |
|---|---|---|
| `--dest FOLDER` | `./uploads` | The folder for the photo sets |
| `--port N` | `8765` | The port for the server |
| `--token TOKEN` | The token in `--token-file` | The access token |
| `--token-file PATH` | `./.photodrop-token` | The file that contains the token. If the file does not exist, Photo Drop makes it with a random token. |
| `--no-browser` | Off | Do not open the QR code page when the server starts |

To change the token, delete `.photodrop-token` and start the server again. After this change, old links do not operate.

If Windows Firewall asks if Python can use the network, give access on **private** networks.

## Security

Use Photo Drop for short periods on a network that you trust, for example your home Wi-Fi network. Read this section before you use Photo Drop.

**Protection**

- Each request must have a random 72-bit access token. The Python `secrets` module makes the token. The server compares tokens in constant time.
- The server can only receive files. It cannot show a list of files, send files, or delete files.
- Photo Drop changes each file name and folder name from the phone to one safe name. Thus, uploads cannot go outside the destination folder.
- The QR code page shows the token. Thus, the server sends this page only to requests from the PC (`127.0.0.1`).

**Limits**

- **Plain HTTP.** Photo Drop does not encrypt the photos or the token during transfer. Do not use it on shared or public Wi-Fi networks.
- **No upload limit.** A person with the token can upload files of up to 4 GB each. This person can continue until the disk is full.
- **QR page and DNS rebinding.** The QR page checks only the source address of the connection. It does not check the `Host` header. Thus, a malicious website in the browser of the PC can possibly read the token with DNS rebinding.
- **The Python `http.server` module** has only basic security checks. It is not for production use.
- Photo Drop keeps the token as plain text in `.photodrop-token`. Your phone also keeps the token in its bookmarks.

When you complete the uploads, stop the server. Push Ctrl+C or close the server window.

## How it operates

The phone page (`index.html`) sends each file in a `POST /upload` request. The file is the raw body of the request. The phone sends two files at the same time. The query string contains the set name and the file name. The `X-Token` header contains the token.

The server (`server.py`) writes each request body to a temporary file. At the same time, it calculates the hash of the file. If the file is a duplicate, the server deletes the temporary file. If the file is not a duplicate, the server moves it to its final location.

## License

Photo Drop has the [MIT](LICENSE) license. This repository includes the [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) QR code library by Kazuhiko Arase. This library also has the MIT license. Refer to [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
