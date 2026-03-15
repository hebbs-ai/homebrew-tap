class Hebbs < Formula
  desc "Cognitive memory engine — store, recall, reflect, and forget knowledge"
  homepage "https://hebbs.dev"
  version "0.3.0"
  license "BSL-1.1"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.0/hebbs-macos-arm64.tar.gz"
      sha256 "31da60e581e09115c67e0468b92639c5dfb0bb06d9fd627f965b439c5e470ea4"
    end
  end

  on_linux do
    if Hardware::CPU.intel?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.0/hebbs-linux-x86_64.tar.gz"
      sha256 "39084617a371d0a3cd79d3fef75f66af16b0771027fdddc3a77181432ab19bbd"
    elsif Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.3.0/hebbs-linux-aarch64.tar.gz"
      sha256 "96e3595e4f225d128acec5824bd646a206b9353eb2fa88d919ca95a66aa8df01"
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
