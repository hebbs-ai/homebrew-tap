class Hebbs < Formula
  desc "Cognitive memory engine — store, recall, reflect, and forget knowledge"
  homepage "https://hebbs.dev"
  version "0.3.1"
  license "BSL-1.1"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.1/hebbs-macos-arm64.tar.gz"
      sha256 "ba24703dbef6c5b32f5f8fd6e919104c7ea6163101159e54d68a17dc2e103dae"
    end
  end

  on_linux do
    if Hardware::CPU.intel?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.1/hebbs-linux-x86_64.tar.gz"
      sha256 "1f118f5d9acb4ec5b8963039c5f0216bb5bbfb312bb08e3f09460ee7876e5c18"
    elsif Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.1/hebbs-linux-aarch64.tar.gz"
      sha256 "6b0fba0139bc2d88dc39187912c5382c8b0bb44c58fc0e05dbf663875de6aa8d"
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
