{
  description = "BGG wishlist availability checker with ntfy notifications";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, pyproject-nix, uv2nix, pyproject-build-systems, ... }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

      pythonSets = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
        in
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope (lib.composeManyExtensions [
          pyproject-build-systems.overlays.default
          overlay
        ]));
    in
    {
      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt);

      packages = forAllSystems (system: {
        default = pythonSets.${system}.mkVirtualEnv "bgg-mm-env" workspace.deps.default;
      });

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/bgg-mm";
        };
      });

      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system}.overrideScope editableOverlay;
          virtualenv = pythonSet.mkVirtualEnv "bgg-mm-dev-env" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            packages = [ virtualenv pkgs.uv ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            };
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
            '';
          };
        });

      nixosModules.bgg-mm = { config, lib, pkgs, ... }:
        let
          cfg = config.services.bgg-mm;
          packageDefault = self.packages.${pkgs.stdenv.hostPlatform.system}.default;

          # Build the config.json from the structured Nix options at evaluation time.
          generatedConfig = pkgs.writeText "bgg-mm-config.json" (builtins.toJSON (
            lib.filterAttrsRecursive (_: v: v != null) {
              bgg = {
                username = cfg.bgg.username;
                wishlist_priorities = cfg.bgg.wishlistPriorities;
                subtypes = cfg.bgg.subtypes;
              };
              shop.base_url = cfg.shop.baseUrl;
              state_file = cfg.stateFile;
              ntfy = if cfg.ntfy.topic != null then lib.filterAttrsRecursive (_: v: v != null) {
                topic    = cfg.ntfy.topic;
                base_url = cfg.ntfy.baseUrl;
                priority = cfg.ntfy.priority;
                tags     = cfg.ntfy.tags;
              } else null;
            }
          ));
        in {
          options.services.bgg-mm = with lib; {
            enable = mkEnableOption "BGG wishlist availability checker";

            package = mkOption {
              type = types.package;
              default = packageDefault;
              description = "Package that provides the bgg-mm CLI.";
            };

            tokenFile = mkOption {
              type = types.path;
              description = ''
                Path to a file containing the BGG API token as a single line:
                  BGG_API_TOKEN=<your-token>
                This file should be owner-readable only (e.g. managed by agenix or sops-nix).
              '';
            };

            schedule = mkOption {
              type = types.str;
              default = "0 7 * * *";
              description = "Systemd OnCalendar expression (cron-style schedule).";
            };

            user = mkOption {
              type = types.str;
              default = "bgg-mm";
              description = "User that should run the checker.";
            };

            extraArgs = mkOption {
              type = types.str;
              default = "";
              description = "Additional command-line arguments passed to the CLI.";
            };

            stateFile = mkOption {
              type = types.str;
              default = "/var/lib/bgg-mm/availability.json";
              description = "Path to the JSON file that tracks already-notified games.";
            };

            bgg = {
              username = mkOption {
                type = types.str;
                description = "BoardGameGeek username whose wishlist is checked.";
              };

              wishlistPriorities = mkOption {
                type = types.nullOr (types.listOf types.int);
                default = null;
                description = "Wishlist priorities to include (1=must have … 5=thinking about it). Null means all.";
              };

              subtypes = mkOption {
                type = types.nullOr (types.listOf types.str);
                default = [ "boardgame" "boardgameexpansion" ];
                description = "BGG collection subtypes to fetch.";
              };
            };

            shop = {
              baseUrl = mkOption {
                type = types.str;
                default = "http://www.moenen-en-mariken.nl";
                description = "Base URL of the shop to scrape.";
              };
            };

            ntfy = {
              topic = mkOption {
                type = types.nullOr types.str;
                default = null;
                description = "ntfy topic to publish to. Leave null to disable notifications.";
              };

              baseUrl = mkOption {
                type = types.nullOr types.str;
                default = null;
                description = "ntfy server base URL. Defaults to https://ntfy.sh when null.";
              };

              priority = mkOption {
                type = types.nullOr types.str;
                default = null;
                description = "ntfy message priority (min/low/default/high/urgent).";
              };

              tags = mkOption {
                type = types.nullOr (types.listOf types.str);
                default = null;
                description = "ntfy message tags/emoji shortcodes.";
              };
            };
          };

          config = lib.mkIf cfg.enable {
            users.users.${cfg.user} = lib.mkIf (cfg.user == "bgg-mm") {
              isSystemUser = true;
              group = "bgg-mm";
              description = "BGG-MM service user";
            };
            users.groups.${cfg.user} = lib.mkIf (cfg.user == "bgg-mm") {};

            systemd.tmpfiles.rules = [
              "d ${builtins.dirOf cfg.stateFile} 0750 ${cfg.user} ${cfg.user} -"
            ];

            environment.systemPackages = [
              (pkgs.writeShellScriptBin "bgg-mm-reset" ''
                exec systemctl start bgg-mm-reset.service
              '')
            ];

            systemd.services.bgg-mm = {
              description = "BGG wishlist availability checker";
              after = [ "network-online.target" ];
              wants = [ "network-online.target" ];
              serviceConfig = {
                Type = "oneshot";
                User = cfg.user;
                ExecStart = "${cfg.package}/bin/bgg-mm --config ${generatedConfig}${lib.optionalString (cfg.extraArgs != "") " ${cfg.extraArgs}"}";
                EnvironmentFile = cfg.tokenFile;
              };
            };

            systemd.services.bgg-mm-reset = {
              description = "BGG wishlist availability checker (force re-notify all)";
              after = [ "network-online.target" ];
              wants = [ "network-online.target" ];
              serviceConfig = {
                Type = "oneshot";
                User = cfg.user;
                ExecStart = "${cfg.package}/bin/bgg-mm --config ${generatedConfig} --reset${lib.optionalString (cfg.extraArgs != "") " ${cfg.extraArgs}"}";
                EnvironmentFile = cfg.tokenFile;
              };
            };

            systemd.timers.bgg-mm = {
              description = "Run BGG-MM on schedule";
              wantedBy = [ "timers.target" ];
              timerConfig = {
                OnCalendar = cfg.schedule;
                Persistent = true;
              };
            };
          };
        };
    };
}
