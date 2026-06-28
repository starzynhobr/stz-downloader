# Privacy Policy — STZ Downloader (browser extension)

_Last updated: 2026-06-28_

STZ Downloader is an open-source download manager. The browser extension's only
job is to hand downloads from your browser to the **STZ Downloader application
running locally on your own computer**.

## What the extension accesses

To send a download to the local app, the extension reads, for the file you are
downloading:

- The **download URL**.
- The page **referrer** and the browser **User-Agent**.
- **Cookies** for that URL — required so that downloads behind a login/session
  work (the same way the browser itself would authenticate the download).

It also stores a small **local setting** (the bridge address and an on/off
toggle) using the browser's `storage` API.

## Where the data goes

All of the above is sent **only** to the STZ Downloader application on your own
machine, over a local connection (`http://127.0.0.1:8765` by default).

- The data is **never** sent to STZ Labs, the developer, or any third party.
- There are **no analytics, no tracking, and no remote servers**.
- Nothing is collected or stored by us. We have no servers that receive your
  data.

If the local application is not running, the extension simply does nothing and
the browser downloads the file normally.

## Permissions and why they are needed

| Permission | Why |
|------------|-----|
| `downloads` | Detect a starting download and cancel it so the local app can take over. |
| `cookies` | Pass your session cookies to the local app so authenticated downloads succeed. |
| `<all_urls>` (host) | Downloads can originate from any site, so the extension must be able to read the request context on any site. |
| `storage` | Save your local preferences (bridge address, enabled toggle). |
| `contextMenus` | Add the "Download with STZ Downloader" right-click item. |

## Data retention

The extension keeps no history. Cookies/URLs are read on the fly for each
download and passed straight to the local app; they are not retained by the
extension.

## Contact

Questions or issues: https://github.com/starzynhobr/stz-downloader/issues
