from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("clipping-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
