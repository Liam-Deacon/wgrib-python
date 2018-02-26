"""
Simple wrapper around main function in wgrib.c
Compile wgrib.c with GRIB_MAIN=wgrib_main defined using c preprocessor
"""
from __future__ import print_function, unicode_literals

import ctypes
import io
import os
import sys
import threading
import time

try:
    from contextlib import redirect_stdout, redirect_stderr
except ImportError:
    from contextlib2 import redirect_stdout, redirect_stderr

from . import wgrib, wgrib2

# Note: OutputGrabber class taken from: 
# https://stackoverflow.com/questions/24277488/in-python-how-to-capture-the-stdout-from-a-c-shared-library-to-a-variable
class OutputGrabber(object):
    """
    Class used to grab standard output or another stream.
    """
    escape_char = "\b"

    def __init__(self, stream=None, threaded=False):
        self.origstream = stream
        self.threaded = threaded
        if self.origstream is None:
            self.origstream = sys.stdout
        self.origstreamfd = self.origstream.fileno()
        self.capturedtext = ""
        # Create a pipe so the stream can be captured:
        self.pipe_out, self.pipe_in = os.pipe()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    def start(self):
        """
        Start capturing the stream data.
        """
        self.capturedtext = ""
        # Save a copy of the stream:
        self.streamfd = os.dup(self.origstreamfd)
        # Replace the original stream with our write pipe:
        os.dup2(self.pipe_in, self.origstreamfd)
        if self.threaded:
            # Start thread that will read the stream:
            self.workerThread = threading.Thread(target=self.readOutput)
            self.workerThread.start()
            # Make sure that the thread is running and os.read() has executed:
            time.sleep(0.01)

    def stop(self):
        """
        Stop capturing the stream data and save the text in `capturedtext`.
        """
        # Print the escape character to make the readOutput method stop:
        self.origstream.write(self.escape_char)
        # Flush the stream to make sure all our data goes in before
        # the escape character:
        self.origstream.flush()
        if self.threaded:
            # wait until the thread finishes so we are sure that
            # we have until the last character:
            self.workerThread.join()
        else:
            self.readOutput()
        # Close the pipe:
        os.close(self.pipe_out)
        # Restore the original stream:
        os.dup2(self.streamfd, self.origstreamfd)

    def readOutput(self):
        """
        Read the stream data (one byte at a time)
        and save the text in `capturedtext`.
        """
        while True:
            char = os.read(self.pipe_out, 1)
            if not char or self.escape_char in char:
                break
            self.capturedtext += char

# _dir = os.path.abspath(os.path.dirname(__file__))

# if sys.platform.startswith('win'):
#     lib_prefix = ''
#     lib_ext = '.dll'
# else:
#     lib_prefix = 'lib'
#     lib_ext = '.so'

# _lib = ctypes.CDLL(os.path.join(_dir, lib_prefix + 'wgrib' + lib_ext))
# _main = _lib.wgrib_main
# _main.restype = ctypes.c_int
# _main.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.POINTER(ctypes.c_char))]

# def wgrib_main(args=sys.argv):
#     argc = len(args)
#     argv = ctypes.c_char_p * (argc+1)
    
#     with OutputGrabber(sys.stdout) as stdout:
#         _main(argc, argv(*[ctypes.c_char_p(arg.encode('utf-8')) for arg in args]))
#     return stdout.capturedtext

# del lib_prefix, lib_ext, _lib, _main
    
def check_wgrib_output(args=sys.argv):
    with OutputGrabber(sys.stdout) as stdout, \
            OutputGrabber(sys.stderr) as stderr:
        wgrib.main(args)
    return stdout.capturedtext, stderr.capturedtext

def check_wgrib2_output(args=sys.argv):
    with OutputGrabber(sys.stdout) as stdout, \
            OutputGrabber(sys.stderr) as stderr:
        wgrib2.main(args)
    return stdout.capturedtext, stderr.capturedtext

del os, sys, ctypes
