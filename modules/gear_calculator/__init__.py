"""Offline external spur gear engineering; public API has no UI/CAD imports."""

from .models import GearSpecification, GearPairSpecification, LoadSpecification
from .calculation import calculate_gear, calculate_pair

__all__ = ['GearSpecification', 'GearPairSpecification', 'LoadSpecification',
           'calculate_gear', 'calculate_pair']
