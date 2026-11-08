# Written by warden's homebrew workflow for each release, from the release's
# signed manifest: https://github.com/pecheriere/warden/blob/main/.github/workflows/homebrew.yml
# This repository's CI checks every checksum here against that manifest.
class Warden < Formula
  desc "Command-line client for the warden approval broker"
  homepage "https://github.com/pecheriere/warden"
  license any_of: ["MIT", "Apache-2.0"]

  on_macos do
    depends_on arch: :arm64

    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.10.0/warden-0.10.0-macos-arm64.tar.gz"
      sha256 "c2e366193fc688c9d600d42d4805815c4bd22d9d8c2f45bf2327fda582ca808a"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/pecheriere/warden/releases/download/v0.10.0/warden-0.10.0-linux-arm64.tar.gz"
      sha256 "8270f8b60c7eef9074c42ac8ef8c48e30283833330bc96e6565f6a242aecec36"
    end
    on_intel do
      url "https://github.com/pecheriere/warden/releases/download/v0.10.0/warden-0.10.0-linux-amd64.tar.gz"
      sha256 "6dc43380c45e09d9e58d47dca41628f76917691bb98be5ff8b5af2445db5d8b7"
    end
  end

  def install
    bin.install "warden"
  end

  test do
    assert_equal "warden #{version}", shell_output("#{bin}/warden --version").strip
  end
end
