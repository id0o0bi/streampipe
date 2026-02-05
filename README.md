# StreamPipe

HTTP server for streaming HLS content using [streamlink](https://github.com/streamlink/streamlink).

## Overview

StreamPipe restreams HLS content over HTTP using streamlink's parallel segment downloading. Unlike ffmpeg which downloads segments sequentially, streamlink uses multiple threads for concurrent downloads, resulting in faster streaming performance.

## Features

- **HTTP server** - Simple REST API for accessing streams
- **Parallel downloading** - Uses streamlink's `stream-segment-threads` for concurrent segment downloads
- **Chunked transfer encoding** - Real-time streaming via HTTP chunked encoding
- **Concurrent clients** - Threading support for multiple simultaneous viewers
- **Simple config** - YAML-based stream configuration
- **No disk storage** - All segment data stays in memory (16MB ring buffer)

## Installation

```bash
# Clone the repository
git clone https://github.com/id0o0bi/streampipe.git
cd streampipe

# Install dependencies
pip install -r requirements.txt

# Or using uv
uv pip install -r requirements.txt
```

### Requirements

- Python 3.7+
- streamlink
- pyyaml

## Quick Start

1. **Copy the example config:**
   ```bash
   cp config.example.yml config.yml
   ```

2. **Edit `config.yml` with your stream URLs:**
   ```yaml
   server:
     host: "0.0.0.0"
     port: 8080

   streams:
     channel1: "https://example.com/stream1.m3u8"
     channel2: "https://example.com/stream2.m3u8"
   ```

3. **Run the server:**
   ```bash
   python pipe.py
   ```

4. **Access your streams:**
   ```
   http://localhost:8080/channel1
   http://localhost:8080/channel2
   ```

## Configuration

Create a `config.yml` file:

```yaml
server:
  host: "0.0.0.0"
  port: 8080

streams:
  nasatv: "https://nasa.com/live.m3u8"
  bloomberg: "https://bloomberg.com/live.m3u8"

options:
  user_agent: "StreamPipe/1.0"
  threads: 4
  timeout: 20.0
  buffer_size: 8192
```

### Options

- `server.host` - Bind address (default: "0.0.0.0")
- `server.port` - Server port (default: 8080)
- `streams` - Map of stream names to URLs
- `options.user_agent` - HTTP user agent
- `options.threads` - Parallel download threads (default: 4)
- `options.timeout` - HTTP timeout in seconds (default: 20.0)
- `options.buffer_size` - Read buffer size (default: 8192)

## Usage

```bash
# Start with default config.yml
python pipe.py

# Use custom config file
python pipe.py -c myconfig.yml

# Override host/port
python pipe.py --host 127.0.0.1 --port 9090
```

## API Endpoints

- `GET /` or `GET /health` - Health check
- `GET /<stream_name>` - Stream content (e.g., `/channel1`)

Stream names must be lowercase letters, numbers, and hyphens only.

## How It Works

```
Client Request → HTTP Server → streamlink → RingBuffer (memory) → Chunked HTTP Response
```

StreamPipe uses streamlink's in-memory RingBuffer (default 16MB) to queue downloaded segments. Data flows directly from the parallel downloader threads to your HTTP response without touching disk.

## Security

- Stream names are validated (lowercase, numbers, hyphens only)
- Path traversal attempts return 404
- Graceful handling of client disconnections

## License

MIT

## Credits

Built with [streamlink](https://github.com/streamlink/streamlink) - the excellent stream extraction library.
Also with OpenCode and Kimi K2.5
