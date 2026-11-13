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
      url "https://github.com/pecheriere/warden/releases/download/v0.13.0/warden-0.13.0-macos-arm64.tar.gz"
      sha256 "e015ab390f386a48576e39a749cc8f5a92647de91e382b89d7c478eb3dafd034"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.13.0/warden-0.13.0-linux-arm64.tar.gz"
      sha256 "6f499f4b595b39e43b46d7201620f810c523ce5f20d7b413e676ba0f9ba1dffe"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.13.0/warden-0.13.0-linux-amd64.tar.gz"
      sha256 "5cca66d87c984358d7fa28166af61fbeeaedf1e2d4e3f3ffff2e0f7e61c523f4"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
