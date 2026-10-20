"""Approximate room-temperature stock densities; user edits belong to the project."""

from .models import Material, Project, Sheet, uid
from weight.materials import MATERIALS as WEIGHT_DENSITIES, MATERIAL_SOURCES as WEIGHT_SOURCES

DENSITIES = (
    ('S235JR', WEIGHT_DENSITIES['S235JR'], WEIGHT_SOURCES['S235JR']),
    ('S355JR', WEIGHT_DENSITIES['S355JR'], WEIGHT_SOURCES['S355JR']),
    ('DX51D', WEIGHT_DENSITIES['DX51D+Z'], WEIGHT_SOURCES['DX51D+Z']+' · Çelik taban; kaplama ayrı hesaplanmaz.'),
    ('AISI 304', WEIGHT_DENSITIES['304'], WEIGHT_SOURCES['304']),
    ('AISI 316', WEIGHT_DENSITIES['316'], WEIGHT_SOURCES['316']),
    ('EN AW-5754', 2660, 'https://www.hydro.com/en/global/aluminium/products/rolled-products/'),
    ('EN AW-5083', 2660, 'https://www.hydro.com/en/global/aluminium/products/rolled-products/'),
)
SIZES = ((1000, 2000), (1250, 2500), (1500, 3000), (2000, 4000))


def new_project():
    return Project(materials=[Material(name, name, density, source) for name, density, source in DENSITIES],
                   sheets=[Sheet(uid(), '1250 × 2500')])
