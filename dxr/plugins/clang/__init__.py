"""Clang Plugin"""

import os
from operator import itemgetter
from itertools import chain

from functools import wraps
from funcy import merge, partial, imap, group_by

from dxr.plugins import FileToIndex
from dxr.plugins.utils import StatefulTreeToIndex
from dxr.plugins.clang.condense import load_csv, build_inhertitance


PLUGIN_NAME = 'clang'


class ClangFileToIndex(FileToIndex):
    def __init__(self, path, contents, tree, inherit):
        super(ClangFileToIndex, self).__init__(path, contents, tree)
        self.inherit = inherit
        condensed = load_csv(*os.path.split(path))
        self.needles, self.needles_by_line = get_needles(condensed, inherit)
        self.refs_by_line = refs(condensed)
        self.annotations_by_line = annotations(condensed)
        

    def needles(self):
        return self.needles

    def needles_by_line(self):
        return self.needles_by_line

    def refs_by_line(self):
        return self.refs_by_line # TODO: look at htmlify.py

    def annotations_by_line(self):
        return self.annotations_by_line # TODO: look at htmlify.py


def refs(_):
    return []


def annotations(_):
    return []


def pluck2(key1, key2, mappings):
    """Plucks a pair of keys from mappings. 
    This is a generalization of funcy's pluck function.

    (k1, k2, {k: v}) -> [(v1, v2)]
    """
    return imap(itemgetter(key1, key2), mappings)


def get_needles(condensed, inherit):
    """Return a pair of iterators (file_needles, line_needles)."""
    needles_ = group_by(len, all_needles(condensed, inherit))
    return needles_[2], needles_[3]

def all_needles(condensed, inherit):
    return []


def get_needle(condensed, tag, key1, key2, field=None, prefix=''):
    if field is None:
        field = tag
        
    prefix = '{0}-'.format(prefix) if prefix else ''

    return ((prefix + tag, key1, key2) for key1, key2
            in pluck2(key1, key2, condensed[field]))

    
class ClangTreeToIndex(StatefulTreeToIndex):
    def __init__(self, tree):
        super(ClangTreeToIndex, self).__init__(tree, clang_indexer)


def clang_indexer(tree):
    vars_ = yield
    # ENV SETUP

    # Setup environment variables for inspecting clang as runtime
    # We'll store all the havested metadata in the plugins temporary folder.
    temp_folder = os.path.join(tree.temp_folder, 'plugins', PLUGIN_NAME)
    plugin_folder = os.path.join(tree.config.plugin_folder, PLUGIN_NAME)
    flags = [
        '-load', os.path.join(plugin_folder, 'libclang-index-plugin.so'),
        '-add-plugin', 'dxr-index',
        '-plugin-arg-dxr-index', tree.source_folder
    ]
    flags_str = " ".join(imap('-Xclang {}'.format, flags))

    env = {
        'CC': "clang %s" % flags_str,
        'CXX': "clang++ %s" % flags_str,
        'DXR_CLANG_FLAGS': flags_str,
        'DXR_CXX_CLANG_OBJECT_FOLDER': tree.object_folder,
        'DXR_CXX_CLANG_TEMP_FOLDER': temp_folder,
    }
    env['DXR_CC'] = env['CC']
    env['DXR_CXX'] = env['CXX']

    yield merge(vars_, env)
    # PREBUILD
    yield # BUILD STEP
    # POSTBUILD
    condensed = load_csv(temp_folder, fpath=None, only_impl=True)
    inherit = build_inhertitance(condensed)
    yield partial(ClangFileToIndex, inherit=inherit)
