{
  description = "Rounded Zellij tab and status bars, derived from the native plugins";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/177d0540942fb205af6993b1d5fa0b57799e09f8";
  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      release = builtins.fromJSON (builtins.readFile ./release.json);
      prebuilt = pkgs.linkFarm "zellij-rounded-bars-${release.version}" (
        pkgs.lib.mapAttrsToList (name: hash: {
          inherit name;
          path = pkgs.fetchurl {
            url = "https://github.com/yongminari/zellij-rounded-bars/releases/download/v${release.version}/${name}";
            inherit hash;
          };
        }) release.artifacts
      );
      projectSource = pkgs.lib.fileset.toSource {
        root = ./.;
        fileset = pkgs.lib.fileset.unions [ ./default-plugins ./support ];
      };
      bars = assert pkgs.zellij-unwrapped.version == "0.45.1";
        pkgs.pkgsCross.wasi32.rustPlatform.buildRustPackage {
          pname = "zellij-rounded-bars";
          version = "0.1.1";
          inherit (pkgs.zellij-unwrapped) src cargoDeps;
          nativeBuildInputs = [ pkgs.python3 ];
          postPatch = ''
            python ${./scripts/prepare.py} ${projectSource} .
          '';
          buildPhase = ''
            runHook preBuild
            export CARGO_TARGET_WASM32_WASIP1_LINKER=${pkgs.rustc.llvmPackages.lld}/bin/lld
            cargo build --offline --release --target wasm32-wasip1 \
              -j "$NIX_BUILD_CORES" -p tab-bar -p status-bar
            runHook postBuild
          '';
          doCheck = false;
          installPhase = ''
            mkdir -p $out
            cp target/wasm32-wasip1/release/tab-bar.wasm $out/rounded-tab-bar.wasm
            cp target/wasm32-wasip1/release/status-bar.wasm $out/rounded-status-bar.wasm
          '';
        };
    in {
      packages.${system} = {
        inherit prebuilt;
        default = bars;
        rounded-bars = bars;
        test-python = pkgs.python3.withPackages (p: [ p.pyte ]);
        zellij = pkgs.zellij;
      };
    };
}
