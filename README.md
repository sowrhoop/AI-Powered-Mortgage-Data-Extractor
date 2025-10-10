# Ascendant Vision AI Platform

Ascendant Vision AI Platform is a Windows desktop app that lets you capture a region of your screen and analyze the image with OpenAI Vision to extract structured mortgage document data (with confidence scores). Results are shown in a side panel where you can review and edit fields.

No local OCR or Transformers models are used — the analysis is performed via the OpenAI API.

## Prerequisites

- Windows 10/11
- Python 3.9+ from https://python.org
- An OpenAI API key with access to vision-capable models

## Installation

1. Clone or download this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

You can provide your API key in either of these ways:

- Environment variable (recommended):
  - PowerShell (current session):
    ```powershell
    $env:OPENAI_API_KEY = "sk-..."
    ```
  - System-wide (Windows): set it in System Properties → Environment Variables.
- In-app settings: Launch the app and use the Settings button to enter your key. The key is stored in plaintext at:
  - `~/.ascendant_vision_ai_platform/settings.json`

Optional environment variable for hotkeys:
- `HOTKEYS` (comma-separated). Defaults to `ctrl+alt+m,ctrl+alt+a`.

## Running

Run from source:
```bash
python src/main.py
```

Usage flow:
- Press one of the hotkeys (defaults: `Ctrl+Alt+M` or `Ctrl+Alt+A`).
- Drag to select a screen region and release to capture.
- The app sends the image to OpenAI and displays extracted fields with confidence scores.
- Edit fields inline if needed.

Notes:
- Global hotkeys may require running as Administrator on Windows. If hotkey registration fails, try launching the app as admin.
- The app is DPI-aware; on high-DPI displays, capture accuracy should be maintained.

## Building an Executable

Use the included PyInstaller script:
```bash
python build.py
```
The single-file executable will be placed under `dist/`.

## Troubleshooting

- Hotkeys not working:
  - Try running the app as Administrator.
  - Ensure no other app is using the same hotkey.
- OpenAI errors (timeouts/rate limits): The app retries with exponential backoff and will display an error in the UI/logs.
- Results window not visible: Check the taskbar/alt-tab; it snaps to the right half of the screen by default.
- Logs: See `ascendant_vision_ai_platform.log` next to the project root for diagnostic messages.

## Privacy & Security

- Images of selected screen regions are sent to OpenAI for analysis. Do not capture sensitive data you are not comfortable sending to the API.
- If you save the API key via Settings, it is stored unencrypted at `~/.ascendant_vision_ai_platform/settings.json`.
