# BGG Wishlist Availability Checker

This script keeps an eye on your BoardGameGeek wishlist and lets you know when one of those games appears as in stock at **Moenen en Mariken**.

## Setup

1. Create an isolated environment with [uv](https://github.com/astral-sh/uv):
   ```bash
   uv venv
   source .venv/bin/activate
   ```
2. Install dependencies and the CLI (this also writes/updates `uv.lock` for the Nix flake):
   ```bash
   uv sync
   ```
3. Copy the sample config and edit it with your details:
   ```bash
   cp config.example.json config.json
   $EDITOR config.json
   ```
   - `bgg.username`: your BoardGameGeek username.
   - `bgg.access_token`: Your BGG API access token (see below for how to get one). You can leave this empty initially and add it once approved.
   - `bgg.wishlist_priorities` (optional): restrict the priorities that are checked.
   - `bgg.subtypes` (optional): list of BGG collection subtypes to fetch; defaults to `["boardgame", "boardgameexpansion"]`.
   - `shop.base_url`: keep the default (`http://www.moenen-en-mariken.nl`) unless the shop domain changes.
   - `ntfy.topic`: the topic name you want to publish to (on `https://ntfy.sh` by default).
   - `ntfy.base_url` (optional): point to a self-hosted ntfy server.
   - `ntfy.tags`, `ntfy.priority`, `ntfy.token` (optional): fine-tune the notification metadata or authenticate.
   - `state_file`: path for the JSON file that tracks previously-seen available games.

## Getting a BGG API Access Token

The BoardGameGeek API now requires authentication. To get an access token:

1. Log in to BoardGameGeek.com
2. Go to **Account Settings** > **API Access**
3. Submit a request for an access token (if you haven't already)
4. Once approved, copy the token and add it to your `config.json` under `bgg.access_token`

**Note**: You can set up your configuration file before receiving the token. The script will give you a clear error message if you try to run it without a valid token, reminding you to add it once you receive it.

## Manual run

```bash
bgg-mm --config config.json
```

If you don't have your access token yet, you'll see a helpful error message with instructions.

Use `--dry-run` to skip publishing to ntfy while still updating the state file and printing results. Turn on verbose logs with `-v`. Add `--debug-dump debug_xml` to keep raw BGG XML responses for troubleshooting.

### Scraper debugging

The shop client is runnable as a small CLI for debugging without involving the full wishlist script:

```bash
uv run python -m bgg_mm.shop --query "Vantage" --dump-dir debug_html -v
```

This reproduces the catalog POST search and the standard lookup flow, printing intermediate results and optionally dumping raw HTML so you can inspect the markup. Use `--detail-code` to fetch a specific `details.php?code=...` page directly.

## Scheduled execution

The script is safe to run as often as you like; it only emails you when something that was previously unavailable becomes available. To run it nightly with cron:

```bash
0 7 * * * /path/to/.venv/bin/bgg-mm --config /path/to/BGG-MM/config.json >> /path/to/BGG-MM/check.log 2>&1
```

Adjust the paths and schedule to your liking. If you're on NixOS, see `flake.nix` for a module that can install the cron job declaratively.

## NixOS integration

The repository ships a Nix flake that relies on [uv2nix](https://github.com/astral-sh/uv2nix) to build the Python application from `pyproject.toml`/`uv.lock`.

- Build the CLI:
  ```bash
  nix build .#bgg-mm
  ./result/bin/bgg-mm --help
  ```
- Drop into a dev shell that provides `uv` and Python:
  ```bash
  nix develop
  ```

To run the checker from a host configuration, import the included NixOS module:

```nix
{
  inputs.bgg-mm.url = "path:/path/to/BGG-MM"; # or e.g. "github:user/BGG-MM";

  outputs = { self, nixpkgs, bgg-mm, ... }: {
    nixosConfigurations.mymachine = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        bgg-mm.nixosModules.bgg-mm
        ({ config, ... }: {
          services.bgg-mm = {
            enable = true;
            user = "bggmm";
            schedule = "0 6 * * *";
            configFile = "/var/lib/bgg-mm/config.json";
            extraArgs = "--verbose";
          };
        })
      ];
    };
  };
}
```

Ensure the referenced `config.json` exists on the target machine and keep `uv.lock` in sync with your Python dependencies (`uv sync` regenerates it) so Nix builds remain reproducible.

## Testing

This project includes a comprehensive test suite to ensure all functionality works correctly.

### Running tests

1. Install test dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
   
   Or with uv:
   ```bash
   uv pip install -e ".[dev]"
   ```

2. Run all tests:
   ```bash
   pytest tests/
   ```

3. Run tests with verbose output:
   ```bash
   pytest tests/ -v
   ```

### Test coverage

The test suite includes:
- **BGG Client Tests**: XML parsing, priority filtering, retry handling, deduplication
- **Shop Client Tests**: URL resolution, catalog search, product detail fetching, availability detection
- **State Management Tests**: Persistence, state updates, JSON format validation
- **Notification Tests**: Message formatting, ntfy integration, authentication
- **Integration Tests**: End-to-end workflow validation

All tests use mocked external dependencies and don't require internet access or real API credentials.

## Notes

- This code was authored without direct access to the Moenen en Mariken site response due to the sandboxed environment. You may need to tweak the CSS selectors in `bgg_mm/shop.py` if the site markup differs from common WooCommerce patterns.
- BoardGameGeek occasionally returns HTTP 202 while it prepares the wishlist export; the script automatically retries for a short time.
- The state file (`data/availability.json` by default) can be deleted if you ever want to receive notifications for current stock again.
