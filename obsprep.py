#!/usr/bin/python

import re, os, shutil, urllib, subprocess
import osc.core, yaml, md5
from debian.changelog import Changelog, Version

m = re.match(r"(?P<first_name>\w+) (?P<last_name>\w+)", "Malcolm Reynolds")


########################################################################
# Abstract class
########################################################################
class OBSBuildRuntimeError(RuntimeError):
    pass

class OBSBuild(object):

    download_url_format = None
    compression_ext = 'gz'
    tarball_strip_components = 1
    changelog_file = 'changelog'

    def __init__(self):
        self.osc = osc.core.Package(os.getcwd())
        self.changelog = self.parse_changelog()
        self.changelog_last = list(self.changelog)[0]
        self.tmp_dir = os.path.join('/tmp', self.name)

    ########################################################################
    # Accessors
    ########################################################################
    @property
    def name(self):
        return self.osc.name

    ########################################################################
    # Tarball operations
    ########################################################################
    @property
    def debian_tarball_url(self):
        raise OBSBuildRuntimeError(
            "Subclasses must implement debian_tarball_url()")

    @property
    def debian_tarball_filename(self):
        return "%s_%s.orig.tar.%s" % \
            (self.name, self.upstream_version, self.compression_ext)

    @property
    def debian_tarball_is_downloaded(self):
        return os.path.exists(self.debian_tarball_filename)

    def debian_tarball_download(self):
        if self.debian_tarball_is_downloaded:
            print "File '%s' already exists" % self.debian_tarball_filename
            return
        print "Downloading file '%s'" % self.debian_tarball_filename
        print "   from URL '%s'" % self.debian_tarball_url
        link = urllib.FancyURLopener()
        link.retrieve(self.debian_tarball_url, self.debian_tarball_filename)

    @property
    def debian_tarball_md5sum(self):
        if not self.debian_tarball_is_downloaded:
            self.debian_tarball_download()
        m = md5.new()
        with open(self.debian_tarball_filename, 'rb') as f:
            while True:
                chunk = f.read(1024*1024)
                if len(chunk) == 0: break
                m.update(chunk)
        return m.hexdigest()

    @property
    def debian_tarball_size(self):
        if not self.debian_tarball_is_downloaded:
            self.debian_tarball_download()
        return  os.path.getsize(self.debian_tarball_filename)

    ########################################################################
    # Changelog operations
    ########################################################################
    def parse_changelog(self):
        c = Changelog()
        with open(self.changelog_file, 'r') as f:
            c.parse_changelog(f)
        return c

    def date_string(self,dt):
        '''Date string suitable for changelog entry'''
        import time
        from email.Utils import formatdate
        tt = dt.timetuple()  # get time.struct_time() object
        ts = time.mktime(tt)  # get timestamp
        return formatdate(ts)  # date string

    @property
    def date_string_now(self):
        import datetime
        return self.date_string(datetime.datetime.now())

    @property
    def upstream_version(self):
        return self.changelog.upstream_version
    
    @property
    def debian_version(self):
        return self.changelog.debian_version
    
    @property
    def debian_tarball_dsc_entry(self):
        return " %s %s %s" % \
            (self.debian_tarball_md5sum,
             self.debian_tarball_size,
             self.debian_tarball_filename)
        
    @property
    def debian_version_next(self):
        raise OBSBuildRuntimeError(
            "Subclasses must implement debian_version_next()")

    @property
    def osc_author(self):
        apiurl = self.osc.apiurl
        osc.conf.get_config()
        userid = osc.conf.config['api_host_options'][apiurl]['user']
        user = osc.core.get_user_data(apiurl, userid, 'realname', 'email')
        return '"%s" <%s>' % tuple(user)

    def debian_changelog_new(self, changes):
        self.changelog.new_block(
            package = self.name,
            version = self.debian_version_next,
            distributions = self.changelog.distributions,
            urgency = self.changelog.urgency,
            changes = changes,
            author = self.osc_author,
            date = self.date_string_now)

    def debian_changelog_write(self, filename):
        with open(filename, 'w') as f:
            self.changelog.write_to_open_file(f)

    ########################################################################
    # Source package operations
    ########################################################################
    def debian_package_source_setup(self):
        # If old directory exists, fail
        if os.path.exists(self.tmp_dir):
            raise OBSBuildRuntimeError(
                "Build directory '%s' exists" % self.tmp_dir)

        # Set up tmp directory, default /tmp/<name>/build
        os.makedirs(self.tmp_dir)

    def debian_package_source_unpack(self):
        # Extract debian source tarball
        tar_cmd = ('tar', 'xCf', self.tmp_dir,
                   self.debian_tarball_filename,
                   '--strip-components=%d' % self.tarball_strip_components,
                   )
        tar_p = subprocess.Popen(tar_cmd)
        tar_p.communicate()
        print "Extracted tarball '%s' to '%s'" % \
            (self.debian_tarball_filename, self.tmp_dir)

    def debian_package_source_debianize(self):
        # Unpack git archive of deb sources into tmpdir
        #
        # Extract tarball of the git tree into tmp directory
        tar_cmd = ('tar', 'xCf', self.tmp_dir, '-')
        tar_p = subprocess.Popen(tar_cmd, stdin=subprocess.PIPE)
        # Create tarball of git tree prefixed with debian/
        git_cmd = ('git', 'archive', '--prefix=debian/', 'HEAD')
        git_p = subprocess.Popen(git_cmd, stdout=tar_p.stdin)
        # Reap processes
        tar_p.communicate()
        git_p.communicate()

        # Copy temp changelog into tmpdir
        self.debian_changelog_write(
            os.path.join(self.tmp_dir, 'debian/changelog'))

        print "Unpacked debian files in '%s/debian'" % self.tmp_dir

    def debian_package_source_configure(self):
        # For subclasses that have an extra source package
        # configuration step
        pass

    def debian_package_dpkg_source(self):
        # Create source package, including *.dsc and *.debian.tar.gz
        dpkg_cmd = ('dpkg-source', '-b', self.tmp_dir)
        dpkg_p = subprocess.Popen(dpkg_cmd)
        dpkg_p.communicate()
        print "Built source package"

    def debian_package_source_clean(self):
        shutil.rmtree(self.tmp_dir)
        print "Removed source package build directory"

    def debian_package_source_build(self):
        self.debian_package_source_setup()
        self.debian_package_source_unpack()
        self.debian_package_source_debianize()
        self.debian_package_source_configure()
        self.debian_package_dpkg_source()
        self.debian_package_source_clean()


########################################################################
# RTAI package
########################################################################
class RTAIOBSBuild(OBSBuild):
    download_url_format = \
        "https://github.com/shabbyx/rtai/archive/%(rev)s.tar.gz"
    upstream_version_re = re.compile(r'(?P<rel>.*)\.(?P<gitrev>[^.]*)')

    @property
    def upstream_release(self):
        m = self.upstream_version_re.match(self.changelog.upstream_version)
        return m.groupdict()['rel']

    @property
    def git_rev(self):
        m = self.upstream_version_re.match(self.changelog.upstream_version)
        return m.groupdict()['gitrev']

    @property
    def debian_tarball_url(self):
        return self.download_url_format % \
            dict(rev = self.git_rev)


    @property
    def debian_version_next(self):
        return Version('%s~%d' % (self.changelog_last.version,
                                  int(self.osc.rev)+1))


if __name__ == '__main__':
    ob = RTAIOBSBuild()

    # Get the tarball if needed
    ob.debian_tarball_download()

    # Init the changelog
    ob.debian_changelog_new(('  * Rebuild in OBS',))

    # Build source package
    ob.debian_package_source_build()
