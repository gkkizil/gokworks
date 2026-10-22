import pytest
from modules.profile_cutting.geometry import Face,verify


def tube(length=1):
    return [Face('plane',(0,0,1)),Face('plane',(0,0,-1),(0,0,length)),Face('cylinder',(0,0,1)),Face('cylinder',(0,0,-1))]


def test_straight_round_profile_uses_plane_distance_in_metres():
    v=verify(tube(),1000)
    assert v.verified and v.length_mm==1000
    assert verify(tube()).verified
    assert not verify(tube(),500).verified


def test_oblique_miter_transverse_cope_and_curved_surfaces_require_review():
    assert not verify(tube()+[Face('plane',(1,0,1))],1000).verified
    assert not verify(tube()+[Face('cylinder',(1,0,0))],1000).verified
    assert not verify(tube()+[Face('torus',(0,0,1))],1000).verified
    assert not verify(tube()+[Face('plane',(0,0,1),(0,0,.5))],1000).verified


def test_ambiguous_solid_cube_is_not_a_length_fallback():
    faces=[]
    for i in range(3):
        axis=tuple(float(j==i) for j in range(3))
        faces.extend([Face('plane',axis),Face('plane',axis,axis)])
    assert not verify(faces).verified


def test_invalid_and_empty_geometry_are_rejected():
    assert not verify([]).verified
    assert not verify([Face('plane',(0,0,0))]).verified


def test_rotated_profile_length_is_independent_of_world_bounding_box():
    from math import sqrt
    axis=(1/sqrt(2),0,1/sqrt(2))
    faces=[Face('plane',axis),Face('plane',axis,axis),Face('cylinder',axis)]
    assert verify(faces,1000).verified
