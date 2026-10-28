"""Uses the existing --gear-worker entry and cancellable service, without Qt."""
def execute(spec,mode,target,folder,construction):
    if mode not in ('check','mesh','dxf','step') or target not in ('pinion','wheel','pair'):
        raise ValueError('Zincir işlemi/hedefi geçersiz.')
    from .geometry import verify
    if mode=='check':return verify(spec)
    if mode=='mesh':
        import numpy as np
        from .cad import placed
        from ..cad import triangulate,compound,shape_stats
        verify(spec);shapes=placed(spec,target)
        np.save(folder/'mesh.npy',np.asarray(triangulate(shapes,.08),dtype='float64'),allow_pickle=False)
        return dict(mode='mesh',chain_included=False,**shape_stats(compound(shapes)))
    if mode in ('dxf','step'):
        from .export import export_cad
        return export_cad(spec,folder/('model.'+mode),target=target,construction=construction)
    raise ValueError('Bilinmeyen zincir dişlisi işlemi.')
