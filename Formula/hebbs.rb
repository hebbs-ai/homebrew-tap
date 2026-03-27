class Hebbs < Formula
  desc "Cognitive memory engine — store, recall, reflect, and forget knowledge"
  homepage "https://hebbs.dev"
  version "0.3.3"
  license "BSL-1.1"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.3/hebbs-macos-arm64.tar.gz"
      sha256 "0c1fc4fe9c3fc8b001308c3f62a397b61af618f6e3d10ad96c4c12ccc0683b14"
    elsif Hardware::CPU.intel?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.3/hebbs-macos-x86_64.tar.gz"
      sha256 "947a5b38025f8834702fbcb2d9f940e3b32c6fdc55432f90493087dad73f8daf"
    end
  end

  on_linux do
    if Hardware::CPU.intel?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.3/hebbs-linux-x86_64.tar.gz"
      sha256 "52a16c547e4d56436eadf8db1b8fb1d7f26a177a326824e761b52d895bc1d3af"
    elsif Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.3/hebbs-linux-aarch64.tar.gz"
      sha256 "5ba4045871c2d9faaa2aa6870a84b929ce70db6104637cce99dc67f2f12bc5de"
    end
  end

  def install
    bin.install "hebbs"
    bin.install "hebbs-bench" if File.exist?("hebbs-bench")
  end

  test do
    assert_match "hebbs", shell_output("#{bin}/hebbs --version")
  end
end
