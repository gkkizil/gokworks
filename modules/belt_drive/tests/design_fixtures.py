"""Synthetic data ONLY. None of these identifiers are real manufacturer products."""

from dataclasses import replace
from modules.belt_drive.catalog.products import ProductSource, BeltProduct, PulleyProduct, ProductCatalog
from modules.belt_drive.catalog.rating_models import RatingTable, CorrectionTable
from modules.belt_drive.design_models import DesignRequest


def source(**changes):
    return ProductSource(**(dict(identifier='test-source', manufacturer='SYNTHETIC ONLY', document='Test arithmetic contract',
        revision='test-1', page='fixture', url='', verification_status='EXAMPLE') | changes))


def timing_catalog(*, rated=False, widths=(10.,), teeth=(28, 58), counts=(160,)):
    belts = tuple(BeltProduct(f'TEST-B-{n}-{w}', 'test:timing', 'test-source', 'HTD_5M', 'test:htd5',
                            tooth_count=n, pitch_mm=5., width_mm=w) for n in counts for w in widths)
    pulleys = tuple(PulleyProduct(f'TEST-P-{n}', 'test:timing', 'test-source', 'HTD_5M', 'test:htd5',
                                 teeth=n, pitch_mm=5., face_width_mm=25., overall_width_mm=30.) for n in teeth)
    rating = RatingTable('test-timing-rating', 'test:timing', 'test-source', 'HTD_5M', 'declared_additive_corrected_v1',
        (20., 80.), (1000., 4000.), ((2., 5.), (8., 11.)), additional_power_kw=0.,
        corrections=(CorrectionTable('engaged_teeth', (1., 100.), (1., 1.), 'linear_declared'),
                     CorrectionTable('length_mm', (100., 5000.), (1., 1.), 'linear_declared'),
                     CorrectionTable('width_mm', (10., 20.), (1., 2.), 'linear_declared')),
        interpolation='bilinear_declared', minimum_pulley=20., maximum_speed_m_s=40.,
        installation_allowance_mm=5., tensioning_allowance_mm=3., method_reference='Synthetic: (base + extra)*factors',
        reference_width_mm=10.)
    return ProductCatalog('synthetic-timing', 'test-1', (source(),), belts, pulleys, (rating,) if rated else ())


def v_catalog(*, rated=False, grooves=1, length=1277.497074474652702607337932219412):
    belts = (BeltProduct('TEST-V-LD', 'test:v', 'test-source', 'A', 'test:A', datum_length_mm=length),)
    pulleys = tuple(PulleyProduct(f'TEST-V-{d}', 'test:v', 'test-source', 'A', 'test:A', datum_diameter_mm=d,
                                 grooves=grooves, face_width_mm=20.*grooves, overall_width_mm=25.*grooves) for d in (100., 200.))
    rating = RatingTable('test-v-rating', 'test:v', 'test-source', 'A', 'declared_additive_corrected_v1',
        (100., 200.), (1450.,), ((2.,), (4.,)), additional_power_kw=.5,
        corrections=(CorrectionTable('wrap_deg', (90., 180.), (1., 1.), 'linear_declared'),
                     CorrectionTable('length_mm', (500., 2000.), (1., 1.), 'linear_declared')),
        interpolation='bilinear_declared', minimum_pulley=80., maximum_speed_m_s=30.,
        installation_allowance_mm=5., tensioning_allowance_mm=3., method_reference='Synthetic additive + factors')
    return ProductCatalog('synthetic-v', 'test-1', (source(),), belts, pulleys, (rating,) if rated else ())


def request(**changes):
    return DesignRequest(**(dict(power_kw=1.5, input_rpm=1450., target_rpm=700., family='timing',
        include_unverified=True, rpm_error_max_percent=.1, service_factor=1.2) | changes))


def with_rating(catalog, **changes):
    return replace(catalog, ratings=(replace(catalog.ratings[0], **changes),))
