"""Dispatch through the existing bounded/cancellable process service."""
def execute(spec,mode,target,folder,construction):
    from .geometry import verify
    if mode=='check':return verify(spec)
    if mode=='mesh':
        import numpy as np
        from ..cad import triangulate,compound,shape_stats
        from .cad import placed
        verify(spec);shapes=placed(spec,target)
        np.save(folder/'mesh.npy',np.asarray(triangulate(shapes,min(.12,spec.module_mm*.05)),dtype='float64'),allow_pickle=False)
        return dict(mode='mesh',**shape_stats(compound(shapes)))
    if mode in ('dxf','step'):
        from .export import export_cad
        return export_cad(spec,folder/('model.'+mode),target=target,construction=construction)
    raise ValueError('Bilinmeyen mekanizma işlemi.')
