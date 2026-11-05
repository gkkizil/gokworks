"""Automatic request/report contracts and v2 projects with v1 input compatibility.

Saved calculations are not authoritative. Projects store inputs, catalogue
snapshots/digests and selection hints; recomputation produces current results.
"""

from dataclasses import asdict, dataclass
import json

from .catalog.importers import construct, catalog_to_dict, catalog_from_dict, fingerprint
from .catalog.products import ProductCatalog, sequence, text
from .design_models import DesignRequest, DesignSearchReport
from .serialization import read_json, to_dict, from_dict, SCHEMA
from .models import BeltDriveSpecification
from .nominal_design import NominalSizingOptions, NominalSizingReport

REQUEST_SCHEMA = SCHEMA + '.automatic_request'


def request_to_dict(request):
    if not isinstance(request, DesignRequest):
        raise ValueError('DesignRequest gerekli.')
    return dict(schema=REQUEST_SCHEMA, version=1, units='mm', **asdict(request))


def request_from_dict(data):
    if not isinstance(data, dict) or data.get('schema') != REQUEST_SCHEMA or type(data.get('version')) is not int or data['version'] != 1 or data.get('units') != 'mm':
        raise ValueError('Otomatik tasarım isteği şema v1 ve mm gerekli.')
    return construct(DesignRequest, {key:value for key,value in data.items() if key not in ('schema','version','units')})


@dataclass(frozen=True, slots=True)
class DesignProject:
    request: DesignRequest | None = None
    catalog: ProductCatalog | None = None
    manual: BeltDriveSpecification | None = None
    selected_ids: tuple[str, ...] = ()
    nominal_options: NominalSizingOptions | None = None

    def __post_init__(self):
        if self.nominal_options is not None and (not isinstance(self.nominal_options,NominalSizingOptions) or self.catalog is not None or not isinstance(self.request,DesignRequest)):
            raise ValueError('Genel boyutlandırma projesi katalog yerine nominal seçenekler ve istek içerir.')
        if self.request is not None and (not isinstance(self.request, DesignRequest) or
                self.nominal_options is None and not isinstance(self.catalog, ProductCatalog)):
            raise ValueError('Otomatik proje için istek ve katalog snapshot gerekli.')
        if self.request is None and self.catalog is not None:
            raise ValueError('Katalog snapshot otomatik istek olmadan kaydedilemez.')
        if self.manual is not None:
            to_dict(self.manual)  # revalidates nominal inputs, including geometry.
        if self.request is self.manual is None:
            raise ValueError('En az manuel veya otomatik tasarım girdisi gerekli.')
        selected = sequence(self.selected_ids, 'Seçilen aday kimlikleri', maximum=5000)
        for value in selected:
            text(value, 'Aday kimliği')
        if len(selected) != len(set(selected)):
            raise ValueError('Aday seçimi tekrarlanamaz.')
        object.__setattr__(self, 'selected_ids', selected)


def project_to_dict(project):
    if not isinstance(project, DesignProject):
        raise ValueError('DesignProject gerekli.')
    result=dict(schema=SCHEMA, version=2, units='mm',
        request=request_to_dict(project.request) if project.request else None,
        catalog=catalog_to_dict(project.catalog) if project.catalog else None,
        catalog_sha256=fingerprint(project.catalog) if project.catalog else None,
        manual=to_dict(project.manual) if project.manual else None, selected_ids=project.selected_ids)
    if project.nominal_options is not None:
        result['version']=3;result['nominal_options']=asdict(project.nominal_options)
    return result


def project_from_dict(data):
    if isinstance(data, dict) and type(data.get('version')) is int and data['version'] == 1:
        return DesignProject(manual=from_dict(data))
    keys = {'schema','version','units','request','catalog','catalog_sha256','manual','selected_ids'}
    if isinstance(data,dict) and type(data.get('version')) is int and data['version']==3:
        keys=keys|{'nominal_options'}
    if not isinstance(data, dict) or set(data) != keys or data['schema'] != SCHEMA or type(data['version']) is not int or data['version'] not in (2,3) or data['units'] != 'mm':
        raise ValueError('Proje şema v1/v2/v3 veya birim/alanlar desteklenmiyor.')
    catalog = catalog_from_dict(data['catalog']) if data['catalog'] is not None else None
    if data['catalog_sha256'] != (fingerprint(catalog) if catalog else None):
        raise ValueError('Katalog snapshot içerik özeti uyuşmuyor; sonuçlar yeniden doğrulanmalı.')
    return DesignProject(request=request_from_dict(data['request']) if data['request'] is not None else None,
        catalog=catalog, manual=from_dict(data['manual']) if data['manual'] is not None else None,
        selected_ids=data['selected_ids'],
        nominal_options=construct(NominalSizingOptions,data['nominal_options']) if data['version']==3 else None)


def project_dumps(project):
    return json.dumps(project_to_dict(project), ensure_ascii=False, allow_nan=False, indent=2)


def project_loads(content):
    return project_from_dict(read_json(content))


def report_to_dict(report, *, selected_ids=None):
    if isinstance(report,NominalSizingReport):
        from .nominal_design import report_to_dict as nominal_dict
        return nominal_dict(report,selected_ids=selected_ids)
    if not isinstance(report, DesignSearchReport):
        raise ValueError('DesignSearchReport gerekli.')
    result = asdict(report)
    result['sources'] = [dict(asdict(source), effective_status=source.effective_status,
                              officially_verified=source.officially_verified) for source in report.sources]
    if selected_ids is not None:
        selected_ids = sequence(selected_ids, 'Rapor seçimi', maximum=5000)
        for identifier in selected_ids:
            text(identifier, 'Rapor aday kimliği')
        available = {item.identifier for item in (*report.capacity_verified, *report.unverified)}
        if len(selected_ids) != len(set(selected_ids)) or not set(selected_ids) <= available:
            raise ValueError('Rapor seçimi güncel, dönen adaylar içinde olmalı.')
        chosen = set(selected_ids)
        for key in ('capacity_verified', 'unverified'):
            result[key] = tuple(item for item in result[key] if item['identifier'] in chosen)
    return dict(schema=SCHEMA + '.automatic_result', version=1, units='mm', **result)


def recalculate_project(project, *, stop=None):
    from .design_search import search_drives
    if project.request is None:
        from .calculation import calculate
        return calculate(project.manual, stop=stop), ()
    if project.nominal_options is not None:
        from .nominal_design import size_drive
        report=size_drive(project.request,project.nominal_options,stop=stop)
    else:
        report = search_drives(project.request, project.catalog, stop=stop)
    available = {item.identifier for item in (*report.capacity_verified, *report.unverified)}
    # Stale selections are not materialized from saved numeric results.
    return report, tuple(identifier for identifier in project.selected_ids if identifier in available)
