#!/bin/sh
# Regenerate Python gRPC stubs from hebbs.proto.
# Requires: pip install grpcio-tools
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROTO_DIR="$PROJECT_ROOT/proto"
OUT_DIR="$PROJECT_ROOT/src/hebbs/_generated"

mkdir -p "$OUT_DIR"

python3 -m grpc_tools.protoc \
    -I "$PROTO_DIR" \
    --python_out="$OUT_DIR" \
    --pyi_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    "$PROTO_DIR/hebbs.proto"

# Fix relative import in generated grpc stub
if [ "$(uname)" = "Darwin" ]; then
    sed -i '' 's/^import hebbs_pb2/from hebbs._generated import hebbs_pb2/' "$OUT_DIR/hebbs_pb2_grpc.py"
else
    sed -i 's/^import hebbs_pb2/from hebbs._generated import hebbs_pb2/' "$OUT_DIR/hebbs_pb2_grpc.py"
fi

echo "Generated stubs in $OUT_DIR"
