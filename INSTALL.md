# Deployment Guide

Admin-facing installation recipe for Book Store Assistant on a Windows PC.
The employee-facing daily-use instructions live in `packaging/README.txt`
(shipped alongside the exe, in Spanish).

## Prerequisites

- An OpenAI API key with a spending cap (for LLM enrichment + validation).
- An ISBNdb API key (Premium plan for the $15/month rate limit).
- Write access to this GitHub repo (to push a release tag).
- A USB stick or equivalent transfer medium.
- Admin access on the target Windows PC for the initial install.

## 1. Build the Windows bundle

On your dev machine:

```bash
git tag v0.1.0                # bump the version for each release
git push origin v0.1.0
```

The `build-windows` GitHub Actions workflow triggers on the tag push,
runs the full test suite, then builds a PyInstaller onedir bundle. Wait
~5-10 minutes, then:

1. Open the repo on GitHub → **Actions** tab.
2. Click the latest `build-windows` run.
3. Scroll to **Artifacts** → download `BookStoreAssistant-windows.zip`.

## 2. Fill in the API keys

On your dev machine, extract the zip. Open `BookStoreAssistant/bsa.toml`
in a text editor and fill in the two key lines:

```toml
openai_api_key = "sk-..."
isbndb_api_key = "..."
```

**Do not commit the filled `bsa.toml` to git.** Only the placeholder
`bsa.toml.example` lives in version control.

## 3. Transfer to USB

Copy the entire `BookStoreAssistant/` folder to the USB. The folder
contains everything needed — Python is bundled.

```
BookStoreAssistant/
├── BookStoreAssistant.exe     ← launch target
├── _internal/                  ← PyInstaller runtime (do not modify)
├── bsa.toml                    ← filled with real keys
├── README.txt                  ← Spanish, for the employee
└── data/
    ├── input/
    └── output/
```

## 4. Install on the bookstore PC

With admin access on the target machine:

1. Copy the `BookStoreAssistant/` folder from USB to `C:\BookStoreAssistant\`.
2. Right-click `BookStoreAssistant.exe` → **Enviar a** → **Escritorio
   (crear acceso directo)**. Rename the shortcut to "Asistente de
   Librería".
3. Double-click the shortcut. Windows SmartScreen will show "Windows
   protegió su PC" (the exe is unsigned). Click **Más información** →
   **Ejecutar de todos modos**. This happens once per machine.
4. Smoke test: click **Examinar...**, pick a small sample CSV (e.g.
   `sample_1.csv`, 25 ISBNs), click **Procesar**. Confirm the three
   output files appear next to the input CSV.

## 5. Hand-off to the employee

- Point them at the desktop shortcut and `README.txt` inside the
  install folder. The Spanish README covers daily operation.
- Tell them NOT to edit `bsa.toml`. If a key rotates, you re-deliver
  a new bundle.

## Rotating keys or updating the app

Same flow: push a new tag (`v0.1.1`), download the new zip, edit the
new `bsa.toml`, copy the folder over the existing `C:\BookStoreAssistant\`.
The desktop shortcut keeps working. Manual edits to `bsa.toml` are
overwritten, so the key file ships fresh each update.

## Threat-model notes

- `bsa.toml` sits in plaintext in an admin-readable location. On a
  shared Windows account any user at the keyboard can read it. Use a
  dedicated OpenAI key with a spending cap so a leak is bounded.
- The exe is unsigned. SmartScreen trips once per machine. A code-
  signing cert (~$100/yr) removes the warning; not worth it for one
  machine.
- Venezuela ISBN agency (prefix 980) is intentionally unrouted — the
  upstream endpoint offers no HTTPS, so those ISBNs fall through to
  the no-match path instead of being fetched in cleartext.

## Rollback

If a release breaks at the bookstore, keep the previous USB handy or
download the last-known-good artifact from GitHub Actions → the prior
tag's run. Extracting over `C:\BookStoreAssistant\` restores the
previous build.
