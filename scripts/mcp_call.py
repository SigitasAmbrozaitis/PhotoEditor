"""Call one PhotoEditor MCP tool, as Claude would, and print its result as JSON.

    uv run python scripts/mcp_call.py set_note '{"photo": "DSCF5437", "text": "checked"}'
    uv run python scripts/mcp_call.py --url http://127.0.0.1:8767/mcp library_status

For trying tools by hand and for the end-to-end test (changes made this way are the AI's: the UI shows a
toast). Exits 1 when the tool reports an error.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import anyio
from mcp import Client
from mcp_types import TextContent

DEFAULT_URL = "http://127.0.0.1:8765/mcp"


async def call(url: str, tool: str, arguments: dict[str, Any]) -> int:
    async with Client(url) as client:
        result = await client.call_tool(tool, arguments)
    if result.structured_content is not None:
        print(json.dumps(result.structured_content, indent=2))
    else:
        texts = [b.text if isinstance(b, TextContent) else f"<{b.type}>" for b in result.content]
        print("\n".join(texts))
    return 1 if result.is_error else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("tool")
    parser.add_argument("arguments", nargs="?", default="{}", help="JSON object")
    args = parser.parse_args()
    sys.exit(anyio.run(call, args.url, args.tool, json.loads(args.arguments)))


if __name__ == "__main__":
    main()
