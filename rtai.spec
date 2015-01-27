%global git_rev 5735b81

Name:		rtai
Version:	4.0.4.%{git_rev}
Release:	0
Summary:	The Real-Time Application Interface
License:	GPL
Group:		System Environment/Kernel
Url:		http://www.rtai.org


Source0:	https://github.com/shabbyx/rtai/archive/rtai_%{version}.orig.tar.gz
Source1:	rtai_config_x86_64
Source2:	rtai_config_i686

BuildRequires:	python, bzip2, automake, autoconf, libtool
BuildRequires:  doxygen, graphviz, comedilib-devel, libxml2, asciidoc, fop
BuildRequires:  docbook-dtds, libxslt
Requires:	kernel-rtai = %{version}
ExclusiveArch:  i586 i686 x86_64


%description

The Real-Time Application Interface is a hard real-time extension to
the Linux kernel, contributed in accordance with the Free Software
guidelines. It provides the features of an industrial-grade RTOS,
seamlessly accessible from the powerful and sophisticated GNU/Linux
environment.


%package devel
Summary: Libraries, includes, etc. to develop RTAI applications
Group: Development/Libraries
Requires: rtai = %{version}-%{release}

%description devel

Libraries, includes, etc. to develop RTAI applications


%package kernel-source
Summary: Sources for building RTAI-enabled kernels
Group: System Environment/Kernel
Requires: rtai-devel = %{version}-%{release}

%description kernel-source

Sources for building RTAI-enabled kernels


%prep
%setup -q -n rtai-%{version} -c
mv RTAI-%{git_rev}*/* RTAI-%{git_rev}*/.??* . && rmdir RTAI-%{git_rev}*


%build
KSRC=%{_sourcedir}/linux

# Set up cflags
CFLAGS+=" -DCONFIG_RTAI_INSTALLDIR=%{_libdir}"
CFLAGS+=" -DCONFIG_RTAI_LINUXDIR=${KSRC}"
%ifarch armv7hl
CFLAGS+=" -march=armv6"
%endif

# Set up a dummy kernel .config
%ifarch armv7hl
CONFIG_OPTION=CONFIG_ARM
%endif
%ifarch x86_64
CONFIG_OPTION=CONFIG_X86_64
%endif
%ifarch i686 i586
CONFIG_OPTION=CONFIG_X86_32
%endif
sed -e "s,^CONFIG_X86_X=,${CONFIG_OPTION}=," \
    $KSRC/.config.x86 > $KSRC/.config
%ifnarch armv7hl
echo "CONFIG_ARCH_PXA=y" >> $KSRC/.config
%endif

autoreconf --install

CFLAGS="${CFLAGS}" \
    %{configure} \
    --includedir=%{_includedir}/rtai \
    --with-linux-dir=$KSRC \
    --disable-leds  --disable-rtailab \
    --enable-fpu --enable-rtdm \
    --enable-doc --enable-dbx
#    --with-module-dir=/lib/modules/${KVERS}/rtai \

make -C base/sched/liblxrt CFLAGS="${CFLAGS}"
make -C base/scripts
make -C doc/doxygen


%install
# Main and -devel packages
%{make_install} -C base/sched/liblxrt
rm -f %{buildroot}%{_libdir}/liblxrt.la
mkdir -p %{buildroot}%{_udevrulesdir}
cat base/ipc/shm/rtai_shm.udev base/ipc/shm/rtai_shm.udev > \
    %{buildroot}%{_udevrulesdir}/90-rtai.rules
mkdir -p %{buildroot}%{_bindir}
install -m 755 base/scripts/rtai-config %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_sysconfdir}/grub.d
install %{_sourcedir}/extras/etc/grub.d/09_rtai \
    %{buildroot}%{_sysconfdir}/grub.d
%{make_install} -C rtai-py pythondir=%{python_sitelib}
chmod a-x %{buildroot}%{python_sitelib}/*.py
%{make_install} -C base/include

# -kernel-source package
mkdir -p %{buildroot}%{_usrsrc}/rtai/patches
tar cjf - \
    ChangeLog README.INSTALL \
    aclocal.m4 configure configure.ac bin \
    GNUmakefile.am GNUmakefile.in GNUmakefile \
    rtai_config.h.in \
    addons base testsuite rtai-lab rtai-py \
    > %{buildroot}%{_usrsrc}/rtai/rtai-source.tar.bz2
find base/arch -name 'hal-linux-*.patch' | \
    xargs -I XXX cp XXX \
    %{buildroot}%{_usrsrc}/rtai/patches
for p in %{buildroot}%{_usrsrc}/rtai/patches/*; do
    gzip -9 $p
done


%files
%doc ChangeLog README.ISOLCPUS README.LINUX_SERVER
%doc README.LXRT_EXTS_IN_USE README.md
%{_bindir}/*
%{_libdir}/liblxrt.so*
%{python_sitelib}/*
%{_udevrulesdir}/90-rtai.rules
%{_sysconfdir}/grub.d/09_rtai

%files devel
%{_includedir}/rtai
%{_libdir}/liblxrt.a

%files kernel-source
%{_usrsrc}/rtai


%changelog
* Tue Jan 27 2015 John Morris <john@zultron.com> - 4.0.4.5735b81-0
- Update to ShabbyX fork
- Bring in sync with Debian package

* Sun Jun 16 2013 John Morris <john@zultron.com> - 3.9-2
- Don't require specfile changes to rebuild against new kernel

* Mon Jun  3 2013 John Morris <john@zultron.com> - 3.9-1
- Requires: specific kernel version
- Create udev entries; don't install device nodes
- Add new 32-bit options to .rtai_config
- Simplify ./configure and make install commands
- Build only for x86 arches
- Tweaks to other tags

* Thu Dec  6 2012 John Morris <john@zultron.com> - 3.9-0
- Initial build

