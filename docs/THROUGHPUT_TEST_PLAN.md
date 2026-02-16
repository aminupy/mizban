# Throughput Validation Plan

This plan validates that Mizban transfer throughput approaches available LAN capacity.

## 1) Establish LAN baseline with iperf3

On receiver host:

```bash
iperf3 -s
```

On sender host:

```bash
iperf3 -c <receiver_ip> -P 4 -t 20
```

Capture:

- `Sender` and `Receiver` throughput in Mbits/sec.
- Convert to MB/s: `MB/s ~= Mbits/sec / 8`.

Example baseline from prior environment: `45-56 Mbits/sec` (~`5-7 MB/s`).

## 2) Prepare large test payload

Create a payload file >= 2 GiB:

Linux/macOS:

```bash
fallocate -l 2G /tmp/mizban-test-2g.bin
```

Fallback:

```bash
dd if=/dev/zero of=/tmp/mizban-test-2g.bin bs=1M count=2048
```

Windows PowerShell:

```powershell
fsutil file createnew $env:TEMP\mizban-test-2g.bin 2147483648
```

## 3) Upload throughput matrix

Run uploads from client UI with `parallel_chunks` set to each value:

- `1`
- `2`
- `4`
- `8` (default)

For each run:

1. Start timer at upload start.
2. Stop timer when file card reaches complete state.
3. Compute throughput `MB/s = file_size_MB / elapsed_seconds`.

Record results in a table.

## 4) Download throughput matrix

Repeat the same matrix using download from UI (parallel range path):

- `1`
- `2`
- `4`
- `8`

Record elapsed time and MB/s.

## 5) Acceptance criteria

- Transfer MB/s at `parallel_chunks=8` should approach iperf3 baseline for large files.
- Throughput should increase from `1` to `4/8` streams unless link already saturated.
- No corruption: downloaded SHA256 matches source SHA256.

SHA256 check:

Linux/macOS:

```bash
sha256sum /path/to/source /path/to/downloaded
```

Windows PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 <path>
```

## 6) Reliability checks during throughput runs

- Upload interruption (disable Wi-Fi mid-transfer) should fail cleanly without server crash.
- Retry a fresh upload immediately after interruption should succeed.
- Concurrent file operations from multiple clients should not corrupt completed files.
