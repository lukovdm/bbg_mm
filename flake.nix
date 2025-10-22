{
  description = "BGG wishlist availability checker with ntfy notifications";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
    uv2nix.url = "github:astral-sh/uv2nix";
    systems.url = "github:nix-systems/default";
  };

  outputs = inputs@{ self, nixpkgs, uv2nix, systems, ... }:
    let
      inherit (nixpkgs.lib) genAttrs;
      eachSystem = genAttrs (import systems);
      mkPkgs = system:
        import nixpkgs {
          inherit system;
          overlays = [ uv2nix.overlays.default ];
        };
    in
    {
      packages = eachSystem (system:
        let
          pkgs = mkPkgs system;
          workspace = pkgs.uv2nix.loadWorkspace {
            root = ./.;
          };
        in
        {
          default = workspace.apps."bgg-mm";
        });

      apps = eachSystem (system:
        {
          default = {
            type = "app";
            program = "${self.packages.${system}.default}/bin/bgg-mm";
          };
        });

      devShells = eachSystem (system:
        let
          pkgs = mkPkgs system;
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.uv
              pkgs.python3
            ];
          };
        });

      nixosModules.bgg-mm = { config, lib, pkgs, ... }:
        let
          cfg = config.services.bgg-mm;
          packageDefault = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
        in {
          options.services.bgg-mm = with lib; {
            enable = mkEnableOption "BGG wishlist availability checker cron job";

            package = mkOption {
              type = types.package;
              default = packageDefault;
              description = "Package that provides the bgg-mm CLI.";
            };

            configFile = mkOption {
              type = types.path;
              description = "Path to the configuration JSON file used by the cron job.";
            };

            schedule = mkOption {
              type = types.str;
              default = "0 7 * * *";
              description = "Cron schedule (min hour dom month dow).";
            };

            user = mkOption {
              type = types.str;
              default = "root";
              description = "User that should run the checker.";
            };

            extraArgs = mkOption {
              type = types.str;
              default = "";
              description = "Additional command-line arguments passed to the CLI.";
            };
          };

          config = lib.mkIf cfg.enable (
            let
              jobScript = pkgs.writeShellScript "bgg-mm-cron" ''
                exec ${cfg.package}/bin/bgg-mm --config ${cfg.configFile}${lib.optionalString (cfg.extraArgs != "") " ${cfg.extraArgs}"}
              '';
            in
            {
              services.cron.enable = true;
              services.cron.systemCronJobs = [
                "${cfg.schedule} ${cfg.user} ${jobScript}"
              ];
            }
          );
        };
    };
}
