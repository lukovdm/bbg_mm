{
  description = "BGG wishlist availability checker with ntfy notifications";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.python3Packages.buildPythonApplication {
            pname = "bgg-mm";
            version = "0.1.0";
            format = "pyproject";
            src = ./.;
            doCheck = false;
            nativeBuildInputs = [
              pkgs.python3Packages.setuptools
              pkgs.python3Packages.wheel
            ];
            propagatedBuildInputs = [
              pkgs.python3Packages.requests
              pkgs.python3Packages.beautifulsoup4
            ];
          };
        });

      apps = forAllSystems (system:
        {
          default = {
            type = "app";
            program = "${self.packages.${system}.default}/bin/bgg-mm";
          };
        });

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.python3
              pkgs.uv
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
