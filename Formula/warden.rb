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
      url "https://github.com/pecheriere/warden/releases/download/v0.11.0/warden-0.11.0-macos-arm64.tar.gz"
      sha256 "1e0750fe614530e3b828388c7013262a9bf97c13fa556b6e22856fb0f8b04fd3"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.11.0/warden-0.11.0-linux-arm64.tar.gz"
      sha256 "c044918c25c475fa2214a0ca8086174633aae51a8dd5b786d838bf402a9015f1"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.11.0/warden-0.11.0-linux-amd64.tar.gz"
      sha256 "6b15bce76a9b86c8bca0ff2fb05ca2a51dd5a491565868f988b31fad26d4d73a"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
