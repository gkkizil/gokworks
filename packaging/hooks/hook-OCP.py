"""Keep the novtk wheel's sibling DLL directory and delvewheel load order intact."""

from PyInstaller.utils.hooks import collect_delvewheel_libs_directory, collect_submodules, copy_metadata

hiddenimports = collect_submodules('OCP') + ['cadquery_ocp_proxy']
datas, binaries = collect_delvewheel_libs_directory('OCP', libdir_name='cadquery_ocp_novtk.libs')
datas += copy_metadata('cadquery-ocp-novtk')
