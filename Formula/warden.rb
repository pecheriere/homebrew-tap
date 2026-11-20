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
      url "https://github.com/pecheriere/warden/releases/download/v0.18.0/warden-0.18.0-macos-arm64.tar.gz"
      sha256 "cd9fd599a28e0b1d846e93929bf40a6ab096e38fc39cfeb164e2d452c298c364"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.18.0/warden-0.18.0-linux-arm64.tar.gz"
      sha256 "7d7ee7908467569d2360e541acf6cde334d71723c9871379183e6b3b895711be"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.18.0/warden-0.18.0-linux-amd64.tar.gz"
      sha256 "c7b785d5520150ef9993ad60abd632476770f5fee13b4ebc6fac2731e5e1ab8c"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
