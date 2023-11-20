# Copyright 2013, 2014, 2015, 2016, 2017, 2020, 2022 Andrzej Cichocki

# This file is part of pyven.
#
# pyven is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyven is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyven.  If not, see <http://www.gnu.org/licenses/>.

from argparse import ArgumentParser
from glob import iglob
from tempfile import mkdtemp
import logging, os, shutil, subprocess

log = logging.getLogger(__name__)
distdir = 'dist'

def main():
    logging.basicConfig(format = "<%(levelname)s> %(message)s", level = logging.DEBUG)
    parser = ArgumentParser()
    parser.add_argument('--plat', required = True)
    parser.add_argument('pyversions', nargs = '+')
    args = parser.parse_args()
    holder = mkdtemp()
    try:
        for pip in sorted(iglob("/opt/python/cp[%s]*/bin/pip" % ''.join(args.pyversions))):
            compatibility = pip.split(os.sep)[3]
            log.info("Make wheel(s) for implementation-ABI: %s", compatibility)
            try:
                subprocess.check_call([pip, '--no-cache-dir', 'wheel', '--no-deps', '-w', holder, '.'])
            except subprocess.CalledProcessError:
                log.warning('Skip implementation-ABI:', exc_info = True)
                continue
            wheelpath, = (os.path.join(holder, n) for n in os.listdir(holder))
            subprocess.check_call(['auditwheel', 'repair', '--plat', args.plat, '-w', distdir, wheelpath])
            plaintarget = os.path.join(distdir, os.path.basename(wheelpath))
            if os.path.exists(plaintarget):
                log.info("Replace: %s", plaintarget)
            shutil.copy2(wheelpath, distdir)
            os.remove(wheelpath)
    finally:
        shutil.rmtree(holder)

if ('__main__' == __name__):
    main()
