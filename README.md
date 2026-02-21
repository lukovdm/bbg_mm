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
   - `bgg.wishlist_priorities` (optional): restrict the priorities that are checked.
   - `bgg.subtypes` (optional): list of BGG collection subtypes to fetch; defaults to `["boardgame", "boardgameexpansion"]`.
   - `shop.base_url`: keep the default (`http://www.moenen-en-mariken.nl`) unless the shop domain changes.
   - `ntfy.topic`: the topic name you want to publish to (on `https://ntfy.sh` by default).
   - `ntfy.base_url` (optional): point to a self-hosted ntfy server.
   - `ntfy.tags`, `ntfy.priority`, `ntfy.token` (optional): fine-tune the notification metadata or authenticate.
   - `state_file`: path for the JSON file that tracks previously-seen available games.

4. Set your BGG API token. Obtain one at <https://boardgamegeek.com/applications> and export it before running:
   ```bash
   export BGG_API_TOKEN=your-token-here
   ```
   Never commit this value. For local development you can put it in a `.envrc` (direnv) file that is git-ignored.

## Manual run

```bash
BGG_API_TOKEN=your-token bgg-mm --config config.json
```

Use `--dry-run` to skip publishing to ntfy while still updating the state file and printing results. Turn on verbose logs with `-v`.

### Scraper debugging

The shop client is runnable as a small CLI for debugging without involving the full wishlist script:

```bash
uv run python -m bgg_mm.shop --query "Vantage" --dump-dir tests/fixtures -v
```

This reproduces the catalog POST search and the standard lookup flow, printing intermediate results and optionally dumping raw HTML so you can inspect the markup. Use `--detail-code` to fetch a specific `details.php?code=...` page directly.

## Scheduled execution

The script is safe to run as often as you like; it only emails you when something that was previously unavailable becomes available. To run it nightly, set `BGG_API_TOKEN` in the service environment and schedule accordingly. On NixOS the included flake module handles everything — see below.

## NixOS integration

The repository ships a Nix flake that uses [uv2nix](https://github.com/pyproject-nix/uv2nix) to build the Python application from `pyproject.toml`/`uv.lock`.

- Build the CLI:
  ```bash
  nix build
  ./result/bin/bgg-mm --help
  ```
- Drop into a dev shell that provides `uv` and a fully-wired virtualenv:
  ```bash
  nix develop
  ```

### Secret token

The BGG API token must **never** be stored in `config.json` or committed to the repository. The NixOS module reads it from an `EnvironmentFile`, which is the standard NixOS pattern for secrets. A typical setup with [agenix](https://github.com/ryantm/agenix) looks like:

```nix
# secrets.nix  (at the repo root, encrypted by agenix)
{ ... }: {
  "bgg-api-token.age".publicKeys = [ yourKey ];
}
```

The secret file should contain exactly one line:

```
BGG_API_TOKEN=your-token-here
```

Then reference it in your NixOS configuration — no separate `config.json` needed, everything is declared in Nix:

```nix
{
  inputs.bgg-mm.url = "github:lukovdm/bbg_mm";

  outputs = { self, nixpkgs, bgg-mm, agenix, ... }: {
    nixosConfigurations.mymachine = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        agenix.nixosModules.default
        bgg-mm.nixosModules.bgg-mm
        ({ config, ... }: {
          age.secrets.bgg-api-token.file = ./secrets/bgg-api-token.age;

          services.bgg-mm = {
            enable    = true;
            tokenFile = config.age.secrets.bgg-api-token.path;
            schedule  = "0 7 * * *";   # systemd OnCalendar syntax

            bgg.username           = "your-bgg-username";
            bgg.wishlistPriorities = [ 1 2 3 ];  # optional; null = all priorities

            # shop.baseUrl defaults to http://www.moenen-en-mariken.nl

            ntfy.topic    = "your-ntfy-topic";
            ntfy.priority = "default";           # optional
            ntfy.tags     = [ "game" "bgg" ];    # optional
            # ntfy.baseUrl = "https://ntfy.sh";  # optional, this is the default
          };
        })
      ];
    };
  };
}
```

The module generates a `config.json` in the Nix store at build time and passes it to the CLI automatically. The module also creates a dedicated `bgg-mm` system user, the state directory, a `systemd.service` of type `oneshot`, and a `systemd.timer` on the given schedule.

To re-send all currently available games (demo / reset):

```bash
sudo bgg-mm-reset
sudo systemctl start bgg-mm.service
```

## Notes

- BoardGameGeek occasionally returns HTTP 202 while it prepares the wishlist export; the script automatically retries for a short time.
- The state file (`/var/lib/bgg-mm/availability.json` by default) tracks already-notified games; delete it or run `bgg-mm-reset` to receive notifications for current stock again.
