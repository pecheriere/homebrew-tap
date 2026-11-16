# Written by this tap's bump workflow for each warden release, from the release's
# signed manifest: https://github.com/pecheriere/homebrew-tap/blob/main/.github/workflows/bump.yml
# This repository's CI checks every checksum here against that manifest.
class Warden < Formula
  desc "Command-line client for the warden approval broker"
  homepage "https://github.com/pecheriere/warden"
  license any_of: ["MIT", "Apache-2.0"]

  on_macos do
    depends_on arch: :arm64

    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.16.0/warden-0.16.0-macos-arm64.tar.gz"
      sha256 "b4450b558c06ed66e55698b38f27f2c968aa1e2785b1732b29103a9159598739"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.16.0/warden-0.16.0-linux-arm64.tar.gz"
      sha256 "85f36e9519ac0b8447e0e9221e23a8bdc4d0156a1b0ed06f5fbcad540f98e3fc"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.16.0/warden-0.16.0-linux-amd64.tar.gz"
      sha256 "f6d7c3bc16a161abf380907674032dd3840cf84943f0712ddab46c1457c47790"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
