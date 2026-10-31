from dataclasses import replace

from modules.dxf_dwg.preview.models import PreviewCache,Request
from .test_preview_ui import payload


def test_snapshot_cache_is_lru_bounded_and_revision_specific(tmp_path):
    path=tmp_path/'part.SLDPRT';path.write_text('fixture');p=payload(path)
    cache=PreviewCache(entries=2)
    a=(Request(str(path),body_ref='A'),(1,2),None)
    b=(Request(str(path),body_ref='B'),(1,2),None)
    c=(Request(str(path),body_ref='A'),(2,3),None)
    cache.put(a,p);cache.put(b,p)
    assert cache.get(a) is p and cache.get(c) is None
    cache.put(c,p)
    assert cache.get(b) is None and cache.size<=cache.maximum
    cache.invalidate_source(str(path));assert not cache.items and cache.size==0

    cache=PreviewCache();cache.put(a,p);charge=cache.size
    cache.maximum=int(charge*1.5);cache.put(b,p)
    assert cache.get(a) is None and cache.get(b) is p and cache.size<=cache.maximum


def test_incomplete_or_oversized_snapshots_are_not_retained(tmp_path):
    path=tmp_path/'part.SLDPRT';path.write_text('fixture');p=payload(path)
    key=(Request(str(path)),(1,2),None);cache=PreviewCache(maximum=100)
    cache.put(key,p);assert not cache.items
    cache=PreviewCache();cache.put(key,replace(p,flat=None));assert not cache.items
    cache.put(key,p);cache.clear();assert not cache.items and cache.size==0
