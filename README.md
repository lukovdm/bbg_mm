# BGG Wishlist Availability Checker

This script keeps an eye on your BoardGameGeek wishlist and lets you know when one of those games appears as in stock at **Moenen en Mariken**.

## Setup

1. Create an isolated environment with [uv](https://github.com/astral-sh/uv):
   ```bash
   uv venv
   source .venv/bin/activate
   ```
2. Install dependencies and the CLI:
   ```bash
   uv sync
   ```
3. Copy the sample config and edit it with your details:
   ```bash
   cp config.example.json config.json
   $EDITOR config.json
   ```
   - `bgg.username`: your BoardGameGeek username.
   - `bgg.wishlist_priorities` (optional): restrict the priorities that are checked.
   - `shop.base_url`: keep the default unless the shop domain changes.
   - `ntfy.topic`: the topic name you want to publish to (on `https://ntfy.sh` by default).
   - `ntfy.base_url` (optional): point to a self-hosted ntfy server.
   - `ntfy.tags`, `ntfy.priority`, `ntfy.token` (optional): fine-tune the notification metadata or authenticate.
   - `state_file`: path for the JSON file that tracks previously-seen available games.

## Manual run

```bash
bgg-mm --config config.json
```

Use `--dry-run` to skip publishing to ntfy while still updating the state file and printing results. Turn on verbose logs with `-v`.

## Scheduled execution

The script is safe to run as often as you like; it only emails you when something that was previously unavailable becomes available. To run it nightly with cron:

```bash
0 7 * * * /path/to/.venv/bin/bgg-mm --config /path/to/BGG-MM/config.json >> /path/to/BGG-MM/check.log 2>&1
```

Adjust the paths and schedule to your liking. If you're on NixOS, see `flake.nix` for a module that can install the cron job declaratively.

## Notes

- This code was authored without direct access to the Moenen en Mariken site response due to the sandboxed environment. You may need to tweak the CSS selectors in `bgg_mm/shop.py` if the site markup differs from common WooCommerce patterns.
- BoardGameGeek occasionally returns HTTP 202 while it prepares the wishlist export; the script automatically retries for a short time.
- The state file (`data/availability.json` by default) can be deleted if you ever want to receive notifications for current stock again.
