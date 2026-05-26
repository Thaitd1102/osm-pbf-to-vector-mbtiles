#!/usr/bin/env python3
"""Serve the local MapLibre page and vector tiles stored in MBTiles."""

import argparse
import mimetypes
import re
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


PROJECT_DIR = Path(__file__).resolve().parent
TILE_PATTERN = re.compile(r"^/tiles/(\d+)/(\d+)/(\d+)\.pbf$")


class MapHandler(BaseHTTPRequestHandler):
    database_path = PROJECT_DIR / "hanoi-center.mbtiles"

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Browsers routinely cancel in-flight tiles while panning or zooming.
            self.close_connection = True

    def do_GET(self):
        path = urlparse(self.path).path
        tile_match = TILE_PATTERN.fullmatch(path)
        if tile_match:
            self.serve_tile(*(int(value) for value in tile_match.groups()))
            return

        if path in {"/", "/index.html"}:
            self.serve_file(PROJECT_DIR / "index.html")
            return

        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def serve_file(self, file_path):
        content = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def serve_tile(self, zoom, column, xyz_row):
        if zoom < 0 or column < 0 or xyz_row < 0 or column >= 2**zoom or xyz_row >= 2**zoom:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid tile coordinates")
            return

        tms_row = (2**zoom - 1) - xyz_row
        with sqlite3.connect(self.database_path) as database:
            tile = database.execute(
                """
                SELECT tile_data
                FROM tiles
                WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
                """,
                (zoom, column, tms_row),
            ).fetchone()

        if not tile:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return

        content = tile[0]
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.mapbox-vector-tile")
        if content[:2] == b"\x1f\x8b":
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main():
    parser = argparse.ArgumentParser(description="Serve the Hanoi Center vector map.")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=8080, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MapHandler)
    print(f"Map available at http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
