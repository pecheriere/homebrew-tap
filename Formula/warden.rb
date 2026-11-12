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
      url "https://github.com/pecheriere/warden/releases/download/v0.12.0/warden-0.12.0-macos-arm64.tar.gz"
      sha256 "a2a77614d9bc8a9caaf905b36282cd34b4c70a73c2a3865be50b2780d0af23fc"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.12.0/warden-0.12.0-linux-arm64.tar.gz"
      sha256 "aea28072a479190c494b9aa56a7edae4499e6b30b9d16ad9eb71cc97d1e61b1e"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.12.0/warden-0.12.0-linux-amd64.tar.gz"
      sha256 "a87bf666bffce424ad3857b8b86a955d194ff48652120ced7602486a806d31a3"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
