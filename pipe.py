#!/usr/bin/env python3
"""
StreamPipe - HTTP server for streaming HLS content using streamlink.
"""

import argparse
import sys
import signal
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Union
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from streamlink.session.session import Streamlink
from streamlink.exceptions import NoPluginError, NoStreamsError, StreamError


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class StreamHandler(BaseHTTPRequestHandler):
    streams_config: Dict[str, Any] = {}
    streamlink_options: Dict[str, Any] = {}

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}", file=sys.stderr)

    def do_GET(self):
        path = self.path.strip("/")

        if path == "" or path == "health":
            self.serve_health_check()
        else:
            self.serve_stream(path)

    def serve_health_check(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            b'{"status": "ok", "streams": '
            + str(len(self.streams_config)).encode()
            + b"}"
        )

    def serve_stream(self, stream_name: str):
        if not all(c.islower() or c.isdigit() or c == "-" for c in stream_name):
            self.send_error(404, "Not Found")
            return

        if stream_name not in self.streams_config:
            self.send_error(404, "Not Found")
            return

        stream_config = self.streams_config[stream_name]
        if isinstance(stream_config, dict):
            url = stream_config.get("url")
        else:
            url = stream_config

        if not url:
            self.send_error(500, f"No URL configured for stream '{stream_name}'")
            return

        session = Streamlink()

        user_agent = self.streamlink_options.get("user_agent", "StreamPipe/1.0")
        threads = self.streamlink_options.get("threads", 4)
        timeout = self.streamlink_options.get("timeout", 20.0)

        session.set_option("http-headers", {"User-Agent": user_agent})
        session.set_option("http-timeout", timeout)
        session.set_option("stream-segment-threads", threads)
        session.set_option("ringbuffer-size", 32 * 1024 * 1024)

        try:
            streams = session.streams(url)

            if not streams:
                self.send_error(404, "No streams available")
                return

            stream = streams.get("best") or list(streams.values())[0]

            self.send_response(200)
            self.send_header("Content-Type", "video/MP2T")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            buffer_size = self.streamlink_options.get("buffer_size", 8388608)
            stream_fd = stream.open()

            try:
                while True:
                    data = stream_fd.read(buffer_size)
                    if not data:
                        break

                    # Ensure we don't split MPEG-TS packets (188 bytes)
                    # Trim to nearest packet boundary
                    ts_packet_size = 188
                    remainder = len(data) % ts_packet_size
                    if remainder != 0 and len(data) > ts_packet_size:
                        data = data[:-remainder]

                    if data:
                        chunk_size = len(data)
                        self.wfile.write(f"{chunk_size:x}\r\n".encode())
                        self.wfile.write(data)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()

                self.wfile.write(b"0\r\n\r\n")

            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                print(
                    f"Client disconnected from stream '{stream_name}'", file=sys.stderr
                )
            finally:
                stream_fd.close()

        except NoPluginError:
            self.send_error(502, "No plugin found for this stream URL")
        except NoStreamsError:
            self.send_error(503, "No streams available from source")
        except StreamError as e:
            self.send_error(500, f"Stream error: {e}")
        except Exception as e:
            self.send_error(500, f"Server error: {e}")


def load_config(config_path: str) -> Dict[str, Any]:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_server(config: Dict[str, Any], host: Optional[str], port: Optional[int]):
    server_config = config.get("server", {})
    bind_host: str = host or server_config.get("host", "0.0.0.0")
    bind_port: int = port or server_config.get("port", 8080)

    streams = config.get("streams", {})
    if not streams:
        print("Warning: No streams configured in config file", file=sys.stderr)

    options = config.get("options", {})

    StreamHandler.streams_config = streams
    StreamHandler.streamlink_options = options

    server = ThreadedHTTPServer((bind_host, bind_port), StreamHandler)

    print(
        f"StreamPipe HTTP Server running on http://{bind_host}:{bind_port}",
        file=sys.stderr,
    )
    print(f"Available streams:", file=sys.stderr)
    for name in streams:
        print(f"  - {name} -> http://{bind_host}:{bind_port}/{name}", file=sys.stderr)
    print(f"\nPress Ctrl+C to stop", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...", file=sys.stderr)
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description="StreamPipe - HTTP server for streaming HLS content using streamlink"
    )

    parser.add_argument(
        "-c",
        "--config",
        default="config.yml",
        help="Config file path (default: config.yml)",
    )

    parser.add_argument(
        "--host", help="Server host (overrides config, default: 0.0.0.0)"
    )

    parser.add_argument(
        "--port", type=int, help="Server port (overrides config, default: 8080)"
    )

    args = parser.parse_args()

    config_path = args.config
    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)

    def signal_handler(sig, frame):
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    run_server(config, args.host, args.port)


if __name__ == "__main__":
    main()
