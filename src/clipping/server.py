"""MCP server entry point — registers all video editing tools."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("clipping", log_level="WARNING")

# Register all tool modules
from clipping.tools import analysis_tools, ffmpeg_tools, audio_tools, elevenlabs_tools

analysis_tools.register(mcp)
ffmpeg_tools.register(mcp)
audio_tools.register(mcp)
elevenlabs_tools.register(mcp)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
