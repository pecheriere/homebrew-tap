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
      url "https://github.com/pecheriere/warden/releases/download/v0.15.0/warden-0.15.0-macos-arm64.tar.gz"
      sha256 "9faa492f8a6d167fad65894f9c563ea222069b06ce689e0da5690e2501df90e8"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.15.0/warden-0.15.0-linux-arm64.tar.gz"
      sha256 "5e45d4a153d7391935b3168ebae037c47ed54da5a95aa730ab25702eec6ed62e"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.15.0/warden-0.15.0-linux-amd64.tar.gz"
      sha256 "15f983d749f06387736e30faf385422b570e918aa82c153287b065dd86c062b0"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
