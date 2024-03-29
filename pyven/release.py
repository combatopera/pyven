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

'Release project to PyPI, with manylinux wheels as needed.'
from . import targetremote
from .checks import EveryVersion
from .pipify import allbuildrequires, InstallDeps, pipify
from .projectinfo import ProjectInfo, SimpleInstallDeps
from .sourceinfo import SourceInfo
from .util import bgcontainer
from argparse import ArgumentParser
from aridity.config import ConfigCtrl
from diapyr.util import singleton
from itertools import chain
from lagoon.program import partial, Program
from pkg_resources import resource_filename
from subprocess import CalledProcessError
from tempfile import NamedTemporaryFile
from venvpool import dotpy, initlogging, Pip, Pool, TemporaryDirectory
import lagoon, logging, os, re, shutil, sys, sysconfig

log = logging.getLogger(__name__)
distrelpath = 'dist'

class Arch:

    def __init__(self, entrypointornone):
        self.entrypoint = [] if entrypointornone is None else [entrypointornone]

def _images():
    archlookup = dict(
        i686 = Arch('linux32'),
        x86_64 = Arch(None),
    )
    archmatch = re.compile("_(%s)$" % '|'.join(map(re.escape, archlookup))).search
    images = {
        'manylinux_2_28_x86_64': '2023-11-13-f6b0c51',
        'manylinux_2_24_x86_64': '2022-12-26-0d38463',
        'manylinux_2_24_i686': '2022-12-26-0d38463',
        'manylinux2014_x86_64': '2020-08-29-f97fd86',
        'manylinux2014_i686': '2020-08-29-f97fd86',
    }
    for plat, imagetag in images.items():
        yield Image(imagetag, plat, archlookup[archmatch(plat).group(1)])

class Image:

    prefix = 'quay.io/pypa/'

    @singleton
    def pythonexe():
        impl = "cp%s" % sysconfig.get_config_var('py_version_nodot')
        return "/opt/python/%s-%s%s/bin/python" % (impl, impl, sys.abiflags)

    def __init__(self, imagetag, plat, arch):
        self.imagetag = imagetag
        self.plat = plat
        self.arch = arch

    def makewheels(self, info): # TODO: This code would benefit from modern syntax.
        from lagoon import docker
        from lagoon.program import NOEOL
        docker_print = docker[partial](stdout = None)
        log.info("Make wheels for platform: %s", self.plat)
        scripts = list(info.config.devel.scripts)
        packages = list(chain(info.config.devel.packages, ['sudo'] if scripts else []))
        # TODO: Copy not mount so we can run containers in parallel.
        with bgcontainer('-v', "%s:/io" % info.projectdir, "%s%s:%s" % (self.prefix, self.plat, self.imagetag)) as container:
            def run(execargs, command):
                docker_print(*chain(['exec'], execargs, [container], self.arch.entrypoint, command))
            if packages:
                try:
                    run([], chain(['yum', 'install', '-y'], packages))
                except CalledProcessError:
                    log.warning("Failed to install dependencies, skip %s wheels:", self.plat, exc_info = True)
                    return
            for script in scripts:
                # TODO LATER: Run as ordinary sudo-capable user.
                dirpath = docker[NOEOL]('exec', container, 'mktemp', '-d') # No need to cleanup, will die with container.
                log.debug("In container dir %s run script: %s", dirpath, script)
                run(['-w', dirpath, '-t'], ['sh', '-c', script])
            docker_print.cp(resource_filename(__name__, 'patchpolicy.py'), "%s:/patchpolicy.py" % container)
            run([], [self.pythonexe, '/patchpolicy.py'])
            docker_print.cp(resource_filename(__name__, 'bdist.py'), "%s:/bdist.py" % container)
            run(['-u', "%s:%s" % (os.geteuid(), os.getegid()), '-w', '/io'], chain([self.pythonexe, '/bdist.py', '--plat', self.plat], info.config.pyversions))

def main():
    initlogging()
    config = ConfigCtrl().loadappconfig(main, 'release.arid')
    parser = ArgumentParser()
    parser.add_argument('--upload', action = 'store_true')
    parser.add_argument('path', nargs = '?', default = '.')
    parser.parse_args(namespace = config.cli)
    info = ProjectInfo.seek(config.path)
    git = lagoon.git[partial](cwd = info.projectdir)
    if git.status.__porcelain():
        raise Exception('Uncommitted changes!')
    log.debug('No uncommitted changes.')
    remotename, _ = git.rev_parse.__abbrev_ref('@{u}').split('/')
    if targetremote != remotename:
        raise Exception("Current branch must track some %s branch." % targetremote)
    log.debug("Good remote: %s", remotename)
    with TemporaryDirectory() as tempdir:
        copydir = os.path.join(tempdir, os.path.basename(os.path.abspath(info.projectdir)))
        log.info("Copying project to: %s", copydir)
        shutil.copytree(info.projectdir, copydir)
        for relpath in release(config, git, ProjectInfo.seek(copydir)):
            log.info("Replace artifact: %s", relpath)
            destpath = os.path.join(info.projectdir, relpath)
            try:
                os.makedirs(os.path.dirname(destpath))
            except OSError:
                pass
            shutil.copy2(os.path.join(copydir, relpath), destpath)

def uploadableartifacts(artifactrelpaths):
    def acceptplatform(platform):
        return 'any' == platform or platform.startswith('manylinux')
    platformmatch = re.compile('-([^-]+)[.]whl$').search
    for p in artifactrelpaths:
        name = os.path.basename(p)
        if not name.endswith('.whl') or acceptplatform(platformmatch(name).group(1)):
            yield p
        else:
            log.debug("Not uploadable: %s", p)

def _warmups(info):
    warmups = [w.split(':') for w in info.config.warmups]
    if warmups:
        # XXX: Use the same transient venv as used for running tests?
        with InstallDeps(info, False, None) as installdeps, Pool(next(iter(info.config.pyversions))).readonlyortransient[True](installdeps) as venv:
            for m, f in warmups:
                with NamedTemporaryFile('w', suffix = dotpy, dir = info.projectdir) as script:
                    script.write("from %s import %s\n%s()" % (m, f.split('.')[0], f))
                    script.flush()
                    venv.run('check_call', ['.'] + installdeps.localreqs, os.path.basename(script.name)[:-len(dotpy)], [], cwd = info.projectdir)

def _runsetup(info, commands):
    with Pool(next(iter(info.config.pyversions))).readonly(SimpleInstallDeps(allbuildrequires(info))) as venv:
        venv.run('check_call', ['.'], 'setup', commands, cwd = info.projectdir) # XXX: Should venvpool automatically include current dir?

def release(config, srcgit, info):
    scrub = lagoon.git.clean._xdi[partial](cwd = info.projectdir, input = 'c', stdout = None)
    scrub()
    version = info.nextversion()
    pipify(info, version)
    EveryVersion(info, False, False, [], False, True).allchecks()
    scrub()
    for dirpath, dirnames, filenames in os.walk(info.projectdir):
        for name in chain(filenames, dirnames):
            if name.startswith('test_'): # TODO LATER: Allow project to add globs to exclude.
                path = os.path.join(dirpath, name)
                log.debug("Delete: %s", path)
                (os.remove if name.endswith('.py') else shutil.rmtree)(path)
    _warmups(info)
    pipify(info, version)
    shutil.rmtree(os.path.join(info.projectdir, '.git'))
    setupcommands = []
    if SourceInfo(info.projectdir).extpaths:
        for image in _images():
            image.makewheels(info)
    else:
        setupcommands.append('bdist_wheel')
    _runsetup(info, setupcommands + ['sdist'])
    artifactrelpaths = [os.path.join(distrelpath, name) for name in sorted(os.listdir(os.path.join(info.projectdir, distrelpath)))]
    if config.upload:
        srcgit.tag("v%s" % version, stdout = None)
        # TODO LATER: If tag succeeded but push fails, we're left with a bogus tag.
        srcgit.push.__tags(stdout = None) # XXX: Also update other remotes?
        with config.token as token:
            Program.text(sys.executable)._m.twine.upload('-u', '__token__', '-p', token, *uploadableartifacts(artifactrelpaths), cwd = info.projectdir, stdout = None, env = Pip.envpatch)
    else:
        log.warning("Upload skipped, use --upload to upload: %s", ' '.join(uploadableartifacts(artifactrelpaths)))
    return artifactrelpaths

if '__main__' == __name__:
    main()
