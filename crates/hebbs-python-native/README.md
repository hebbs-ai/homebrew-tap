# hebbs-python-native

PyO3 native extension that embeds the HEBBS engine directly inside a Python process. This crate compiles Rust code into a Python-loadable shared library via [maturin](https://www.maturin.rs/).

**This is NOT the public Python SDK.** Most users should install the pure-Python gRPC client instead:

```bash
pip install hebbs
```

The `hebbs` package on PyPI is a lightweight gRPC client that talks to a running `hebbs-server`. It lives in the separate [`hebbs-python`](https://github.com/hebbs-ai/hebbs-python) repository.

## When to use this crate

Use `hebbs-python-native` only if you need to embed the full HEBBS storage engine inside your Python process without running a separate server. This is an advanced use case -- it requires compiling Rust and links the entire engine (RocksDB, HNSW index, embedding runtime) into the Python extension.

## Building

```bash
cd crates/hebbs-python-native
python -m venv .venv && source .venv/bin/activate
pip install maturin
maturin develop --release
```

## Running tests

```bash
source .venv/bin/activate
pip install pytest
python -m pytest tests/ -v
```
