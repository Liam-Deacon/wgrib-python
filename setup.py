from __future__ import print_function

import os
import sys
import tarfile

# To use a consistent encoding
from codecs import open
from glob import glob
from os import path
from tempfile import gettempdir

from six.moves import urllib
from io import BytesIO, StringIO

# Always prefer setuptools over distutils
from setuptools import Extension, find_packages, setup

here = path.abspath(path.dirname(__file__))

scripts_dir = here + '/' + 'scripts/'

isWindows = lambda: sys.platform.startswith('win')

# crude OS dependent path fixing
if isWindows():
    fix_path = lambda x: x.replace(here + '/', '')  #'"%s"' % x.replace('/', '\\')
else:
    fix_path = lambda x: x.replace(' ', r'\ ')

# get (and slightly modify) wgrib source
wgrib_url = 'ftp://ftp.cpc.ncep.noaa.gov/wd51we/wgrib/wgrib.c'
wgrib2_url = 'ftp://ftp.cpc.ncep.noaa.gov/wd51we/wgrib2/wgrib2.tgz'
define = b'''
#ifndef GRIB_MAIN
#define GRIB_MAIN main
#endif

'''
if not os.path.exists(here + '/src/wgrib.c'):
    print('Downloading wgrib source code...')
    request = urllib.request.urlopen(wgrib_url)
    with open(here + '/src/wgrib.c', 'wb') as wgrib_src:
        src = BytesIO(request.read())
        c_main = b'int main(int argc, char **argv)'
        wgrib_src.write(src.getvalue().replace(c_main, define + c_main.replace(b'main', b'GRIB_MAIN')))

if not os.path.isdir(here + '/src/grib2'):
    print('Downloading wgrib2 source code...')
    request = urllib.request.urlopen(wgrib2_url)
    wgrib2_tgz = BytesIO(request.read())
    wgrib2_tgz.seek(0)
    tar = tarfile.open(fileobj=wgrib2_tgz, mode='r:gz').extractall(path=here + '/src')


# build native executables - have to get hands a little dirty
grib_sources = [here + '/' +  'src/wgrib.c']
grib_exe = 'wgrib'
if 'clean' in sys.argv:
    try:
        print('remove {}'.format(repr(scripts_dir + grib_exe)))
        os.unlink(scripts_dir + grib_exe)
    except IOError:
        pass

if 'build_ext' in sys.argv:
    try:
        from numpy.distutils import ccompiler, fcompiler, log

        # get compilers
        cc = ccompiler.new_compiler()
        fc = fcompiler.new_fcompiler()
        log.set_verbosity(1)  # show compilation commands

        # build sources
        print('Building wgrib...')        
        grib_objs = cc.compile(list(map(fix_path, grib_sources)), output_dir=gettempdir())
        cc.link_executable(grib_objs, grib_exe, 
                           libraries=[] if isWindows() else ['m'],
                           output_dir=fix_path(here + '/' + 'scripts'))
        libgrib_objs = cc.compile(list(map(fix_path, grib_sources)), 
                                  macros=[('GRIB_MAIN', 'wgrib_main')], 
                                  output_dir=gettempdir())
        cc.link_shared_lib(libgrib_objs, grib_exe,
                           libraries=[] if isWindows() else ['m'],
                           output_dir=fix_path(here + '/' + 'tprt'),
                           extra_postargs=['/DLL', '/INCLUDE:wgrib_main', '/EXPORT:wgrib_main'] if isWindows() else [])
        
        print('Building wgrib2...')
        os.environ['CC'] = os.environ.get('CC', cc.compiler[0])
        os.environ['FC'] = os.environ.get('FC', fc.command_vars.get('compiler_f90') or fc.command_vars.get('compiler_f77'))
        try:
            curdir = os.path.abspath('.')
            os.chdir(here + '/src/grib2')
            os.system('make')
        finally:
            os.chdir(curdir)

        
    except ImportError:
        print('Numpy is needed to compile wgrib executable', file=sys.stderr)

# build c extensions
grib_ext = Extension('wgrib.wgrib_c_ext', sources=['src/wgrib.c', 'src/pywgrib.c'],
                     macros=[('GRIB_MAIN', 'wgrib_main')], 
                     libraries=[] if isWindows() else ['m'])

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

with open(path.join(here, 'LICENSE.txt'), encoding='utf-8') as f:
    license = f.readlines()

with open(path.join(here, 'VERSION'), encoding='utf-8') as f:
    version = f.read().strip('\n')

setup(
    name='wgrib',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=version,

    description='Simple python wgrib wrapper',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/Lightslayer/wgrib-python',

    # Author details
    author='Liam Deacon',
    author_email='liam.m.deacon@gmail.com',

    # Choose your license
    license=license[0],

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    # What does your project relate to?
    keywords='wgrib weather GRIB',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=open(path.join(here, 'requirements.txt')).read().split('\n'),

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': ['check-manifest', 'pyflakes', 'flake8'],
        'test': ['coverage'],
    },

    # Extension modules
    ext_modules=[grib_ext],

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
        path.join('scripts', 'wgrib'): path.join(here, 'scripts', grib_exe)
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[(path.join('data', 'static'), 
                 glob(path.join(here, 'data', 'static', '*')))],

    #scripts=[path.join('scripts', grib_exe)],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'wgrib=wgrib:main',
        ],
    },
)
