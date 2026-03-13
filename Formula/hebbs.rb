class Hebbs < Formula
  desc "Cognitive memory engine — store, recall, reflect, and forget knowledge"
  homepage "https://hebbs.dev"
  version "0.2.0"
  license "BSL-1.1"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.2.0/hebbs-macos-arm64.tar.gz"
      sha256 "f668e491d96c8f33da442c24251fca0ea24f8525873d543745ff8817c9954ff8"
    end
  end

  on_linux do
    if Hardware::CPU.intel?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.2.0/hebbs-linux-x86_64.tar.gz"
      sha256 "d20b064a8ef239dc67158d0f0d29274be46fca3dd5ad02791c34e1ba0d390317"
    elsif Hardware::CPU.arm?
      url "https://github.com/hebbs-ai/hebbs/releases/download/v0.2.0/hebbs-linux-aarch64.tar.gz"
      sha256 "48cadeb0a194dedafa0a0e470734800797008c0ffe670626f845aa2e7eb3d5a1"
    end
  end

  def install
    bin.install "hebbs-server"
    bin.install "hebbs-cli"
    bin.install "hebbs-bench" if File.exist?("hebbs-bench")
    (var/"hebbs/data").mkpath
  end

  def post_install
    (var/"log").mkpath
  end

  service do
    run [opt_bin/"hebbs-server", "start", "--data-dir", var/"hebbs/data"]
    keep_alive true
    environment_variables HEBBS_AUTH_ENABLED: "false"
    log_path var/"log/hebbs.log"
    error_log_path var/"log/hebbs.log"
    working_dir var/"hebbs"
  end

  def caveats
    <<~EOS
      To start HEBBS as a background service:
        brew services start hebbs

      Data is stored in #{var}/hebbs/data
      Logs are written to #{var}/log/hebbs.log
      gRPC port: 6380, HTTP port: 6381
    EOS
  end

  test do
    assert_match "hebbs-cli", shell_output("#{bin}/hebbs-cli --version")
  end
end
