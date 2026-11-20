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
      url "https://github.com/pecheriere/warden/releases/download/v0.18.1/warden-0.18.1-macos-arm64.tar.gz"
      sha256 "c60822020de3a76259551293a689fa0d00e3adc168d08a95656f0afa37354daa"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.18.1/warden-0.18.1-linux-arm64.tar.gz"
      sha256 "6b5538351d711329137e4bbac586439316448aba9cbaa688e5f442e579bcb5eb"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.18.1/warden-0.18.1-linux-amd64.tar.gz"
      sha256 "09ecd922574408f71b5fc4dc4077118243e7abaf963a23b226f4190ef67b0447"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
