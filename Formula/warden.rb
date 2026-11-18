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
      url "https://github.com/pecheriere/warden/releases/download/v0.17.0/warden-0.17.0-macos-arm64.tar.gz"
      sha256 "a3acc1f9da5dbae790994ea8365a903e2592cab3c5cf78e653cb9c36c0a21e55"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.17.0/warden-0.17.0-linux-arm64.tar.gz"
      sha256 "586fe920c5f8607cb9b4a3e73b7605e16be1fc93e9f02b9b02358fa73bf5cd7b"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.17.0/warden-0.17.0-linux-amd64.tar.gz"
      sha256 "9da0017d467af1f9b053be6196dd9beb0b0cf902df077a9c562432a0b7d7e0b7"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
