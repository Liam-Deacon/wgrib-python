wgrib-python - A thin Python wrapper for wgrib
==============================================

Install
-------

To build please run:

```pip install wgrib-python```

For configuring wgrib2, `CC` and `FC` environment variables need to set prior to calling `pip`, e.g.

```bash

export CC=gcc-7
export FC=gfortran-7

```

Example
-------

To use try the following python code:

```python

from wgrib import wgrib_main  # wgrib1
import shlex

output = wgrib_main(shlex.split('-text -verf'))
print(output)

```

TODO
----

- Full wgrib2 support
- Fancier wrappings for more flexibility
