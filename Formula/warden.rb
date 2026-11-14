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
      url "https://github.com/pecheriere/warden/releases/download/v0.14.0/warden-0.14.0-macos-arm64.tar.gz"
      sha256 "3b639299b47e40951ebb0d941d211373ffbf727d2a047925769f550d6987b58d"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.14.0/warden-0.14.0-linux-arm64.tar.gz"
      sha256 "7df48e353688f4932d95db7fdbbb29cda74abc6c1d02ee22a22473f0794b6e7b"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.14.0/warden-0.14.0-linux-amd64.tar.gz"
      sha256 "00df3ce04b578e68f74ecdac1be498d6e15f24d78d100bd7e19ce5160f3f6c76"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
