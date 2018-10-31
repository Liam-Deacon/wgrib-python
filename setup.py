#! /usr/bin/python
from __future__ import print_function

import re
import os
import sys
import tarfile
import shutil
import glob
import fnmatch
import platform
import subprocess

# To use a consistent encoding
from codecs import open
from os import path
from tempfile import gettempdir

from six.moves import urllib
from io import BytesIO, StringIO

# Always prefer setuptools over distutils
from setuptools import find_packages, setup
from distutils.errors import LinkError, CompileError
from numpy.distutils.core import Extension

from distutils.sysconfig import get_python_inc

PATH_LIST_SEP = ':' if not sys.platform.startswith('win') else ';'
PYTHON_INCLUDE_PATH = os.environ.get('C_INCLUDE_PATH',
                                     '') + PATH_LIST_SEP + get_python_inc()
os.environ['C_INCLUDE_PATH'] = PYTHON_INCLUDE_PATH

# default is to build and install
if len(sys.argv) < 2:
    sys.argv += ['build_ext', 'build', 'install']

# define some useful variables and functions
here = path.abspath(path.dirname(__file__))
scripts_dir = path.join(here, 'scripts')

isWindows = lambda: sys.platform.startswith('win')
isLinux = lambda: sys.platform.startswith('linux')
toAscii = lambda x: x if isinstance(x, bytes) else bytes(x.encode('ascii'))
BITS = int(platform.architecture()[0].strip('bit'))

# crude OS dependent path fixing
if isWindows():
    fix_path = lambda x: x.replace(here + '/', '')  #'"%s"' % x.replace('/', '\\')
else:
    fix_path = lambda x: x.replace(' ', r'\ ')

# add clean up
if 'clean' in sys.argv:
    for i in ['src/wgrib.c', 'src/pywgrib2.c', 'src/grib2', 'src/wgrib2.tgz'] + \
                list(glob.glob(path.join(scripts_dir, 'wgrib*'))):
        p = here + '/' + i if not os.path.isabs(i) else i
        print('remove {}'.format(p))
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.unlink(p)
        except OSError:
            pass

# get (and slightly modify) wgrib source
wgrib_url = 'ftp://ftp.cpc.ncep.noaa.gov/wd51we/wgrib/wgrib.c'
wgrib2_url = 'ftp://ftp.cpc.ncep.noaa.gov/wd51we/wgrib2/wgrib2.tgz'
c_main = b'int main(int argc, char **argv)'
define = b'''
#ifndef GRIB_MAIN
#define GRIB_MAIN main
#endif

'''
BDS_unpack_mod = bytes(r'(\*\*\*\\n\", n\);\n)[\t ]+exit\(8\);\n[\t ]+for'.encode('ascii'))
if 'build_ext' in sys.argv and not os.path.exists(here + '/src/wgrib.c'):
    print('Downloading wgrib source code...')
    request = urllib.request.urlopen(wgrib_url)
    with open(here + '/src/wgrib.c', 'wb') as wgrib_src:
        src = BytesIO(request.read().replace(c_main, define + c_main.replace(b'main', b'GRIB_MAIN')))
        try:
            src = re.sub(BDS_unpack_mod, b'\\1\treturn;\tfor', src.getvalue())
        except:
            src = re.sub(bytes(BDS_unpack_mod.encode('ascii')), b'\\1\treturn;\tfor', src.getvalue())
        src = src.replace(b'exit(', b'return(')
        
        wgrib_src.write(src)

if 'build_ext' in sys.argv and not isWindows() and not os.path.isdir(here + '/src/grib2'):
    tarfilepath = os.path.join(here, 'src', os.path.basename(wgrib2_url))
    if not os.path.exists(tarfilepath):
        print('Downloading wgrib2 source code...')
        request = urllib.request.urlopen(wgrib2_url)
        with open(tarfilepath, 'wb') as tgz:
            tgz.write(request.read())
    print('Extracting src/{}...'.format(os.path.basename(tarfilepath)))
    with tarfile.open(tarfilepath, mode='r:gz') as tgz:
        for name in tgz.getnames():
            print('extracting src/{}'.format(name))
            tgz.extract(name, path=here + '/src')

# build c extensions
grib_ext = Extension('wgrib.wgrib', sources=[path.join('src', 'wgrib.c'), path.join('src', 'pywgrib.c')],
                     define_macros=[('GRIB_MAIN', 'wgrib')] + 
                                    ([('MS_WIN64', 1)] if isWindows() and BITS == 64 else []), 
                     libraries=[] if isWindows() else ['m'])
extensions = [grib_ext]

# build native executables - have to get hands a little dirty
grib_sources = [path.join(here, *x) for x in [('src', 'wgrib.c'),]]
grib_exe = 'wgrib'

if 'build_ext' in sys.argv:
    try:
        from numpy.distutils import ccompiler, fcompiler, log

        # get compilers
        cc = ccompiler.new_compiler()
        log.set_verbosity(1)  # show compilation commands

        # build sources
        print('\nBuilding wgrib...')
        if not isWindows():
            # clunky hack to force position independent code on *nix systems
            for var in ['CFLAGS', 'FFLAGS', 'LDFLAGS']:
                flags = os.environ.get(var, '-fPIC')
                flags += ' -fPIC' if '-fPIC' not in flags else ''
                os.environ[var] = flags  

        try:
            grib_objs = cc.compile(list(map(fix_path, grib_sources)), output_dir=gettempdir())
            cc.link_executable(grib_objs, grib_exe, 
                            libraries=[] if isWindows() else ['m'],
                            output_dir=fix_path(path.join(here, 'scripts')))
            libgrib_objs = cc.compile(list(map(fix_path, grib_sources)), 
                                    macros=[('GRIB_MAIN', 'wgrib')], 
                                    output_dir=gettempdir())
            cc.link_shared_lib(libgrib_objs, grib_exe,
                            libraries=[] if isWindows() else ['m'],
                            output_dir=fix_path(path.join(here, 'wgrib')),
                            extra_postargs=['/DLL', '/INCLUDE:wgrib', '/EXPORT:wgrib'] if isWindows() else ['-fPIC'])
        except LinkError as err:
            print(err, file=sys.stderr)

        
        if not isWindows():  # wgrib2 currently only supports GNU toolchain
            try:
                print('\nBuilding wgrib2...')
                fc = fcompiler.new_fcompiler()
                env = os.environ.copy()
                env['CC'] = env.get('CC', cc.compiler[0])
                env['FC'] = env.get('FC', fc.command_vars.get('compiler_f90') or fc.command_vars.get('compiler_f77'))

                # modify files for wgrib2
                with open('src/pywgrib.c', 'rb') as src, open('src/pywgrib2.c', 'wb') as dest:
                    code = src.read().replace(b'grib', b'grib2')
                    dest.write(code.replace(b'int wgrib2(int argc, char **argv);',
                                            b'int wgrib2(int argc, const char **argv);'))
                
                # workaround as environment is not exported correctly to subprocess.call
                env['wFFLAGS'] = env['FFLAGS']
                env['wCPPFLAGS'] = '-DGFORTRAN' if 'gfortran' in env['FC'] else ''
                if not path.exists('src/grib2/makefile.orig'):
                    shutil.copy2('src/grib2/makefile', 'src/grib2/makefile.orig')
                with open('src/grib2/makefile.orig', 'rb') as orig_makefile, \
                        open('src/grib2/makefile', 'wb') as makefile:
                    code = orig_makefile.read()
                    code = code.replace(b'#export CC=gcc', b'export CC=' + toAscii(env['CC']), 1)
                    code = code.replace(b'#export FC=gfortran', 
                                        b'export FC=%s\nexport wFFLAGS=%s' % (toAscii(env['FC']), toAscii(env['wFFLAGS'])), 1)
                    code = code.replace(b'wFFLAGS:=""\n', b'#wFFLAGS:=""')
                    code = code.replace(b'USE_IPOLATES=1', b'USE_IPOLATES=0')
                    makefile.write(code)

            except LinkError as err:
                print(err, file=sys.stderr)
    
            try:
                curdir = os.path.abspath('.')
                os.chdir(here + '/src/grib2')
                if subprocess.call(['make'], env=env, shell=True) == 0:
                    subprocess.call(['make lib'], env=env, shell=True)
                    os.chdir('lib')
                    #if isLinux():
                    grib2_objs = []
                    for root, dirnames, filenames in os.walk('src/grib2'):
                        for filename in fnmatch.filter(filenames, '*.o'):
                            grib2_objs.append(os.path.join(root, filename))
                    #else:  # Darwin
                    #    grib2_objs = [ar for ar in os.listdir('.') if ar.endswith('.a')]
                    grib2_ext = Extension('wgrib.wgrib2', 
                        define_macros=[('GRIB_MAIN', 'wgrib2'),
                                       ('CALLABLE_WGRIB2', 1)],
                        sources=['src/pywgrib2.c', 
                                 'src/grib2/wgrib2/wgrib2.c',
                                 'src/grib2/wgrib2/fnlist.c'],
                        include_dirs=['src/grib2/wgrib2', 'src/grib/include'],
                        library_dirs=['src/grib2/lib'], 
                        libraries=[a.split('.a')[0].replace('lib', '') for a in grib2_objs] + ([
                            'gomp', 'gfortran'] if 'gfortran' in env['FC'] else [])
                        )
                    extensions += [grib2_ext]

                    cc.link_shared_lib(grib2_objs, grib_exe.replace('grib', 'grib2'),
                        libraries=[] if isWindows() else ['m'],
                        output_dir=fix_path(here + '/' + 'wgrib'),
                        extra_postargs=['/DLL', '/INCLUDE:wgrib2', 
                                        '/EXPORT:wgrib2'] if isWindows() else ['-fPIC'])
                else:
                    print('\nFailed to make wgrib2', file=sys.stderr)
            except LinkError as err:
                # Seems to be an -fPIC issue
                print(err, file=sys.stderr)
            finally:
                os.chdir(curdir)

        
    except ImportError:
        print('Numpy is needed to compile wgrib executable', file=sys.stderr)

try:
    grib2_sources = glob.iglob('src/grib2/**/*', recursive=True)
except TypeError:
    try:
        import glob2
        grib2_sources = glob2.iglob('src/grib2/**/*', recursive=True)
    except (ImportError, TypeError):
        grib2_sources = []
        for root, dirnames, filenames in os.walk('src/grib2'):
            for filename in fnmatch.filter(filenames, '*'):
                grib2_sources.append(os.path.join(root, filename))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

with open(path.join(here, 'LICENSE.txt'), encoding='utf-8') as f:
    license = f.readlines()

with open(path.join(here, 'VERSION'), encoding='utf-8') as f:
    version = f.read().strip('\n')

setup(
    name='wgrib-python',

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
    ext_modules=extensions,

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
        'requirements.txt': 'requirements.txt',
        'LICENSE.txt': 'LICENSE.txt',
        'VERSION': 'VERSION',
        'wgrib': glob.glob(path.join(here, 'wgrib', 'wgrib*')),
        path.join('src', 'grib2'): grib2_sources,
        path.join('scripts', 'wgrib'): path.join(here, 'scripts', grib_exe)
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[(path.join('data', 'static'), 
                 glob.glob(path.join(here, 'data', 'static', '*')))],

    #scripts=[path.join('scripts', grib_exe)],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'wgrib=wgrib.wgrib:main',
            'wgrib2=wgrib.wgrib2:main'
        ],
    },
)
