# Audio Recording Architecture

This document explains the technical decisions, challenges, and implementation details for the audio recording feature in LocalWriter.

## The Challenge: Native Dependencies in LibreOffice

LocalWriter is a LibreOffice extension. It runs embedded inside LibreOffice's internal Python interpreter. This environment is highly constrained:
1. **No `pip` or Virtual Environments:** Users cannot easily run `pip install` to add dependencies to the LibreOffice Python environment.
2. **Cross-Platform Constraints:** The extension is distributed as a single `.oxt` file that must work universally across Windows, macOS, and Linux.
3. **C-Extensions:** Recording audio typically requires native C libraries (like PortAudio) to interface with the OS audio subsystem (CoreAudio, WASAPI, ALSA). Pure Python cannot record audio.

## Why `sounddevice` and Vendoring?

We evaluated several approaches for cross-platform audio capture:
1. **Web-based input (MediaRecorder API):** Requires hosting a local webpage and asking the user to open their browser to record. Poor UX.
2. **Subprocess OS tools (`arecord`, `sox`, `PowerShell`):** Relies on external commands that might not be installed, behave inconsistently across OS versions, or pop up annoying console windows (Windows).
3. **Bundle a standalone Go/Rust binary:** Increases extension size and adds a second build pipeline outside of Python.
4. **Vendor Python Wheels (`sounddevice`):** The chosen solution.

We opted to **vendor** the pre-compiled `.whl` (wheel) files for `sounddevice`, `cffi`, and `pycparser` directly into the extension under `plugin/vendor/`.

### Why `sounddevice` over `PyAudio`?
`PyAudio` requires PortAudio to be installed on the system to compile. However, the `sounddevice` wheels for Windows and macOS actually bundle the compiled PortAudio binaries (`portaudio.dll` / `libportaudio.dylib`) inside the wheel itself (`_sounddevice_data/`). This makes it completely plug-and-play on Mac and Windows without any compilation or system dependencies.

### The Linux "Gotcha"
On Linux, `sounddevice` does not bundle PortAudio because Linux audio subsystems vary wildly. It expects the system package manager to provide it.
To handle this gracefully, we wrap the import in a `try/except OSError` block. If `libportaudio` is missing on Linux, the extension still loads fine, but when the user clicks "Record", it shows a friendly error asking them to run `sudo apt install libportaudio2`.

### Dynamic Path Injection
To make LibreOffice Python load these vendored wheels, `plugin/main.py` and `panel_factory.py` dynamically inject the `plugin/vendor` folder into `sys.path` at startup:
```python
_vendor_dir = os.path.join(_ext_root, "plugin", "vendor")
if _vendor_dir not in sys.path:
    sys.path.insert(0, _vendor_dir)
```

## Implementation Details

### 1. `AudioRecorder` without `numpy`
The standard way to use `sounddevice` is with `numpy` arrays. However, `numpy` is massive (~30MB compressed) and complex to vendor.
Instead, our `AudioRecorder` uses `sounddevice.RawInputStream` with `dtype='int16'`. This forces `sounddevice` to yield raw `bytes` (PCM data) directly from the CFFI layer. We can then pipe these raw bytes directly into Python's built-in `wave` module in a background thread, creating a standard 16kHz mono `.wav` file with zero heavy dependencies.

### 2. UI: The Dynamic Send/Record Button
To keep the UI clean, we didn't add a dedicated "Record" button. Instead, we attached an `XTextListener` (`QueryTextListener` in `panel.py`) to the text input box.
- If the box is empty, the button says **"Record"**.
- The moment the user types a character, it swaps to **"Send"**.
- Clicking "Record" swaps the label to **"Stop Rec"**.

### 3. Payload & History Database
When the recording stops, `client.py` reads the `.wav` file and converts it to a base64 string. It is injected into the payload using the standard OpenAI multimodal format (`{"type": "input_audio", ...}`).

**Crucial Database Optimization:** A 10-second audio clip base64-encoded is hundreds of kilobytes. If we saved the raw API payload to the SQLite history database (`localwriter_history.db`), the file would quickly bloat to gigabytes, severely degrading extension load times.
In `history_db.py` -> `message_to_dict`, we intercept the message before saving. We strip out any `input_audio` dictionaries and append a simple `[Audio Attached]` tag to the text string. This keeps the database tiny while still indicating in the UI history that audio was used.
