class Hebbs < Formula
  desc "Cognitive memory engine — store, recall, reflect, and forget knowledge"
  homepage "https://hebbs.dev"
  version "0.1.2"
  license "BSL-1.1"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.1.2/hebbs-macos-arm64.tar.gz"
      sha256 "4cd9afb58ec8049b650227de5d6ae92a2199c1c58b1d01503e0f24cf9c3167c6"
    end
  end

  on_linux do
    if Hardware::CPU.intel?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.1.2/hebbs-linux-x86_64.tar.gz"
      sha256 "ca14c99f4ba7a94904c9844dbd835530ed0cfeb811107d5a984e9224881c309d"
    elsif Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.1.2/hebbs-linux-aarch64.tar.gz"
      sha256 "3e071734f4dde71cabf5a5746ea6a141dae096f4d4cd79534be446b665c322d9"
    end
  end

  def install
    bin.install "hebbs-server"
    bin.install "hebbs-cli"
    bin.install "hebbs-bench" if File.exist?("hebbs-bench")
  end

  test do
    assert_match "hebbs-cli", shell_output("#{bin}/hebbs-cli --version")
  end
end
