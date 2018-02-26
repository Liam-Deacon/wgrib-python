import sys

try:
    from .wgrib2 import main
except ImportError:
    from .wgrib import main

main(sys.argv)
