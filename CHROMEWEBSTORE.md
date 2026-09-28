# Chrome Web Store & Mozilla AMO Listing — STZ Downloader Integration

> Last Updated: 2026-09-11
> Extension Version: 0.1.10

This document contains all listing copy, exact permissions justifications, privacy disclosures, and submission checklists required for publishing the extension to the **Chrome Web Store** and **Mozilla Add-ons (AMO)**.

---

## 1. Store Listing Metadata

**Extension Name** [REQUIRED]
```text
STZ Downloader integration
```

**Short Description** [REQUIRED] (Max 132 chars)
```text
Intercepts browser downloads and forwards them to the STZ Downloader desktop application powered by aria2.
```

**Detailed Description** [REQUIRED]
```text
STZ Downloader Integration seamlessly connects your browser to the STZ Downloader desktop application, bringing multi-connection, high-speed downloads powered by aria2 directly to your browsing workflow.

Key Features:
- Automatic Download Interception: Catches file downloads as they start and hands them off to the desktop app.
- Context Menu Integration: Right-click any link, image, or media item and select "Download with STZ Downloader".
- Authenticated Download Support: Forwards session cookies and request headers so private downloads (cloud drives, forums, portals) download without authentication failure.
- Native Messaging Bridge: Ultra-fast local communication between the browser and your desktop application.
- Easy Control: Toggle interception on or off anytime directly from the toolbar popup.

How to Use:
1. Make sure the STZ Downloader desktop application is installed and running on your PC.
2. Click the extension icon in your browser toolbar to verify the status shows "connected".
3. Download any file normally or right-click a link and choose "Download with STZ Downloader".
4. The file will automatically open in STZ Downloader with accelerated multi-connection downloading.

Privacy & Security:
This extension operates 100% locally. It contains no tracking, no analytics, and communicates only with your local machine (127.0.0.1 and native messaging host). No browsing history, personal data, or files are ever sent to remote third-party servers.

Support & Source Code:
Source code and issues: https://github.com/starzynhobr/stz-downloader
Support: https://stzlabs.com
```

**Category** [REQUIRED]
```text
Productivity
```

**Single Purpose** [REQUIRED]
```text
Captures browser downloads and forwards them to the local STZ Downloader desktop application.
```

**Primary Language** [REQUIRED]
```text
English
```

---

## 2. Permissions Justification (CWS Review Team)

Every permission declared in `manifest.json` requires an explicit, plain-English justification. Use the following texts in the Chrome Developer Dashboard:

| Permission | Type | Justification for Reviewer |
| :--- | :--- | :--- |
| `downloads` | `permissions` | Needed to listen to `chrome.downloads.onCreated`, pause/cancel the browser's default download, and redirect the download task to the local STZ Downloader desktop application. |
| `cookies` | `permissions` | Needed to read session cookies for the specific origin URL of the download and forward them to aria2, ensuring authenticated downloads (e.g. from cloud storage or private portals) complete successfully. |
| `storage` | `permissions` | Needed to save user preferences locally within the browser, such as enabling or disabling automatic download interception. |
| `contextMenus` | `permissions` | Needed to create the "Download with STZ Downloader" right-click context menu item on links, images, and audio/video elements. |
| `nativeMessaging` | `permissions` | Needed to communicate directly and securely with the local desktop application helper (`stz-downloader-native-host.exe`) via standard I/O framing. |
| `<all_urls>` | `host_permissions` | Required to intercept file downloads originating from any website across the internet that the user chooses to download from, and to extract origin headers and session cookies for those downloads. |

---

## 3. Privacy & Data Use Disclosure

**Does the extension collect user data?**
> **No.** The extension does not collect or transmit personal data.

### Data Types Checklist:
- Personally identifiable info: **No**
- Health info: **No**
- Financial / Payment info: **No**
- Authentication info: **Temporary local transmission only** (cookies are read from browser storage and transmitted strictly across loopback/native messaging to the local desktop app to authenticate the download request; never transmitted off the user's device).
- Personal communications: **No**
- Location: **No**
- Web history: **No** (The extension does not track or store browsing history).
- User activity / Analytics: **No**

### Privacy Policy URL [REQUIRED]:
```text
https://github.com/starzynhobr/stz-downloader/blob/main/PRIVACY.md
```
*(Or the hosted equivalent on GitHub Pages / stzlabs.com)*

---

## 4. Graphics & Assets Checklist

| Asset | Dimensions | Requirement | Status | File Location |
| :--- | :--- | :--- | :--- | :--- |
| Store Icon | 128×128 PNG | **Required** | ✅ Ready | `extension/icons/icon128.png` |
| Screenshot 1 | 1280×800 PNG | **Required** | ✅ Ready | `assets/screenshots/screenshot_1_main.png` (Main Dashboard) |
| Screenshot 2 | 1280×800 PNG | Recommended | ✅ Ready | `assets/screenshots/screenshot_2_settings.png` (Settings Drawer) |
| Screenshot 3 | 1280×800 PNG | Recommended | ✅ Ready | `assets/screenshots/screenshot_3_confirm.png` (Download Confirm Prompt) |
| Screenshot 4 | 1280×800 PNG | Recommended | ✅ Ready | `assets/screenshots/screenshot_4_popup.png` (Extension Integration Popup) |
| Small Promo Tile | 440×280 PNG | Recommended | ✅ Ready | `assets/screenshots/small_promo_tile.png` (CWS Card Banner) |
| Marquee Tile | 1400×560 PNG | Optional | ⬜ Optional | For featured placement on Web Store homepage |

---

## 5. Submission Step-by-Step

### A. Chrome Web Store (Initial Upload)
1. **Prepare ZIP**:
   Run:
   ```bash
   python scripts/package_extension.py
   ```
   Output: `dist/stz-extension-chrome-0.1.10.zip`.
2. **First Upload Note ("key" field)**:
   - For a **brand-new** item, the Chrome Web Store dashboard will reject a manifest containing the `"key"` attribute.
   - If rejected, temporarily remove `"key"` from `extension/manifest.chrome.json`, run `python scripts/package_extension.py`, and upload the zip.
   - Once created, the CWS will assign an official extension ID.
   - Retrieve the official ID (or the public key string from the "Package" tab in the dashboard).
   - If the ID changed, update `CHROME_EXTENSION_ID` in `src/stz_downloader/native_host.py` and rebuild the installer.
3. **Fill Listing**:
   Copy the texts from Section 1, Section 2, and Section 3 into the Chrome Developer Dashboard.
4. **Upload Assets**:
   Upload `extension/icons/icon128.png` and at least 1 screenshot (1280×800).
5. **Submit for Review**.

### B. Mozilla Firefox AMO
1. **Prepare ZIP**:
   Run:
   ```bash
   python scripts/package_extension.py
   ```
   Output: `dist/stz-extension-firefox-0.1.10.zip`.
2. **Submit to AMO**:
   Log into [addons.mozilla.org](https://addons.mozilla.org/) -> "Submit a New Add-on".
3. **Select Distribution**:
   Choose "On this site" (public AMO listing) or "On your own" (self-distributed XPI).
4. **Source Code**:
   When asked if source code is needed, select **No** because the extension uses unminified, readable vanilla JavaScript.
5. **Gecko ID**:
   AMO recognizes the ID `stz-downloader@stzlabs.com` declared in `manifest.firefox.json` and keeps it consistent with the desktop app's registry configuration.

---

## 6. Next Release Checklist

- **Firefox `strict_min_version`:** bump `browser_specific_settings.gecko.strict_min_version` in `extension/manifest.firefox.json` from `115.0` to `140.0`. AMO warns that `data_collection_permissions` is only supported from Firefox 140 (Android 142); 115 was kept for the 0.1.10 submission.
- Store IDs: Chrome `jhahaknbmgkbnhfnknclelilaoobmpcm`, Firefox `stz-downloader@stzlabs.com`. Updates are uploaded as new versions of the existing items; the listing stays as is.
