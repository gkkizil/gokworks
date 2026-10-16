"""A deliberately separate, active-part-only translation of the typed C# probe.

COM is imported only in connect(), so validation and transaction tests also run
on Linux. All actual calls use wrappers generated from the running SW typelib.
"""
from __future__ import annotations

import argparse
import json
import math
import ntpath
import sys
from pathlib import Path


class ProbeError(RuntimeError):
    pass


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ProbeError(f"{label}: finite JSON number required")
    return float(value)


def validate_snapshot(raw):
    required = {"feature_name", "feature_type", "thickness_mm", "radius_mm", "bend_allowance_type"}
    payloads = {"k_factor", "bend_allowance_mm", "bend_deduction_mm", "bend_table_file"}
    if not isinstance(raw, dict) or not required <= set(raw) or set(raw) - required - payloads:
        raise ProbeError("expected_state must be a sheet-metal readback snapshot")
    state = {**dict.fromkeys(payloads), **raw}
    for key in ("feature_name", "feature_type"):
        if not isinstance(state[key], str) or not state[key].strip():
            raise ProbeError(f"expected_state.{key}: nonempty string required")
    for key in ("thickness_mm", "radius_mm"):
        state[key] = number(state[key], f"expected_state.{key}")
    if state["thickness_mm"] <= 0 or state["radius_mm"] < 0 or type(state["bend_allowance_type"]) is not int:
        raise ProbeError("expected_state contains invalid sheet-metal dimensions or allowance type")
    member = {1: "bend_table_file", 2: "k_factor", 3: "bend_allowance_mm", 4: "bend_deduction_mm"}.get(state["bend_allowance_type"])
    if member == "bend_table_file":
        if not isinstance(state[member], str):
            raise ProbeError("expected_state.bend_table_file must be a string")
    elif member is not None:
        state[member] = number(state[member], f"expected_state.{member}")
    return state


def validate_request(raw):
    if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise ProbeError("schema_version must be 1")
    request = dict(raw)
    unknown = set(request) - {"schema_version", "mode", "document_path", "configuration", "feature_name", "expected_state", "assignments", "tolerance_mm"}
    if unknown:
        raise ProbeError(f"Unknown request fields: {', '.join(sorted(unknown))}")
    request.setdefault("mode", "inspect")
    if request.get("mode") not in ("inspect", "verify", "apply"):
        raise ProbeError("mode must be inspect, verify or apply")
    for key in ("document_path", "configuration", "feature_name"):
        if request.get(key) is not None and (not isinstance(request[key], str) or not request[key].strip()):
            raise ProbeError(f"{key}: nonempty string required")
    if request.get("document_path") and not request["document_path"].lower().endswith(".sldprt"):
        raise ProbeError("document_path must identify a saved .SLDPRT file")
    if request.get("expected_state") is not None:
        request["expected_state"] = validate_snapshot(request["expected_state"])
    tolerance = number(request.get("tolerance_mm", 0.01), "tolerance_mm")
    if tolerance <= 0:
        raise ProbeError("tolerance_mm must be positive")
    request["tolerance_mm"] = tolerance
    rows = request.get("assignments", [])
    if not isinstance(rows, list):
        raise ProbeError("assignments must be an array")
    validated = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ProbeError(f"assignments[{index}] must be an object")
        if set(row) != {"thickness_mm", "k_factor", "radius_mm"}:
            raise ProbeError(f"assignments[{index}] requires exactly thickness_mm, k_factor, radius_mm")
        values = {key: number(row.get(key), f"assignments[{index}].{key}")
                  for key in ("thickness_mm", "k_factor", "radius_mm")}
        if values["thickness_mm"] <= 0 or not 0 <= values["k_factor"] <= 1 or values["radius_mm"] < 0:
            raise ProbeError(f"assignments[{index}]: thickness > 0, 0 <= K <= 1 and radius >= 0 required")
        if any(abs(previous["thickness_mm"] - values["thickness_mm"]) <= 2 * tolerance
               for previous in validated):
            raise ProbeError("Thickness matching intervals overlap")
        validated.append(values)
    if request["mode"] != "inspect" and not validated:
        raise ProbeError("verify/apply requires at least one assignment")
    request["assignments"] = validated
    return request


def error_info(error):
    result = {"type": type(error).__name__, "message": str(error)}
    if hasattr(error, "hresult"):
        result["hresult"] = error.hresult
    return result


def report_template():
    return {"schema_version": 1, "engine": "python", "status": "error",
            "scope": "active_configuration_selected_sheetmetal_definition", "files_saved": False,
            "document_path": None, "configuration": None, "feature": None,
            "assignment": None, "before": None, "after": None,
            "rollback": {"attempted": False, "verified": False, "status": "not_needed", "restored_state": None, "error": None},
            "features": [], "calls": [], "warnings": [], "error": None}


class Trace:
    def __init__(self, report):
        self.entries = report["calls"]

    def call(self, name, operation):
        entry = {"operation": name, "success": False, "detail": None, "error": None, "hresult": None}
        self.entries.append(entry)
        try:
            result = operation()
            entry["success"] = True
            if result is None or type(result) in (bool, int, float, str):
                entry["detail"] = str(result) if result is not None else None
            elif isinstance(result, (tuple, list)) and all(type(x) in (bool, int, float, str, type(None)) for x in result):
                entry["detail"] = json.dumps(result, ensure_ascii=False)
            return result
        except Exception as error:
            entry["error"] = str(error)
            entry["hresult"] = getattr(error, "hresult", None)
            raise


class EarlyBound:
    def __init__(self, client, pythoncom, module, trace):
        self.client, self.pythoncom, self.module, self.trace = client, pythoncom, module, trace
        self.interface_classes = {}
        self.null_component = client.VARIANT(pythoncom.VT_DISPATCH, None)
        self.empty_configurations = client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, ())

    def cast(self, obj, interface):
        if obj is None:
            raise ProbeError(f"{interface}: API returned NULL")
        # Some SW releases expose coclass aliases, but only a declared typelib
        # name is ever used. Never infer member signatures from a generic object.
        names = self.module.NamesToIIDMap
        declared = interface if interface in names else interface[1:]
        if declared not in names:
            raise ProbeError(f"Running SolidWorks typelib has no {interface}")
        # This is the final typed-class construction performed by CastTo.
        # CastTo(..., explicit_typelib) regenerates the typelib on every call;
        # use EnsureModule's full generated classes directly and cache them.
        # Passing a dynamic wrapper here would suppress DispatchBaseClass's QI.
        raw = getattr(obj, "_oleobj_", obj)
        if declared not in self.interface_classes:
            interface_class = getattr(self.module, declared)
            self.interface_classes[declared] = getattr(interface_class, "default_interface", interface_class)
        interface_id = getattr(self.interface_classes[declared], "CLSID", None)
        if interface_id is None:
            raise ProbeError(f"{declared}: generated interface has no IID")
        # pywin32's generated base class tolerates failed QI internally. Make
        # this check explicit so a wrong interface can never look early-bound.
        queried = self.trace.call(f"QueryInterface({declared})", lambda: raw.QueryInterface(
            interface_id, self.pythoncom.IID_IDispatch))
        return self.trace.call(f"GeneratedInterface({declared})", lambda: self.interface_classes[declared](queried))


def connect(trace):
    if sys.platform != "win32":
        raise ProbeError("Native SolidWorks checks require Windows and a running SolidWorks instance")
    from k_factor.standalone.runtime import prepare_generated_cache
    trace.call("PrepareWritableGeneratedCache", prepare_generated_cache)
    import pythoncom
    import win32com.client as client

    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    try:
        app = trace.call("GetActiveObject(SldWorks.Application)", lambda: client.GetActiveObject("SldWorks.Application"))
        typelib = trace.call("RunningSolidWorks.GetTypeInfo.GetContainingTypeLib",
                             lambda: app._oleobj_.GetTypeInfo().GetContainingTypeLib()[0])
        guid, lcid, _platform, major, minor, _flags = typelib.GetLibAttr()
        module = trace.call("gencache.EnsureModule", lambda: client.gencache.EnsureModule(
            guid, lcid, major, minor, bValidateFile=True, bForDemand=False))
        if module is None:
            raise ProbeError("Could not generate running SolidWorks type library wrappers")
        binding = EarlyBound(client, pythoncom, module, trace)
        return binding.cast(app, "ISldWorks"), binding, pythoncom.CoUninitialize
    except Exception:
        pythoncom.CoUninitialize()
        raise


def same_path(left, right):
    return ntpath.normcase(ntpath.normpath(left)) == ntpath.normcase(ntpath.normpath(right))


class Probe:
    def __init__(self, app, binding, report):
        self.app, self.binding, self.report = app, binding, report
        self.trace = Trace(report)
        self.model = None
        self.mutation_attempted = False
        self.radius_dimension_name = None

    def call(self, name, operation):
        return self.trace.call(name, operation)

    def cast(self, obj, interface):
        return self.binding.cast(obj, interface)

    def identity(self):
        model = self.cast(self.call("ISldWorks.ActiveDoc", lambda: self.app.ActiveDoc), "IModelDoc2")
        if self.call("IModelDoc2.GetType", model.GetType) != 1:
            raise ProbeError("Open a saved part as the active SolidWorks document; assemblies are not supported by this probe")
        path = self.call("IModelDoc2.GetPathName", model.GetPathName)
        if not isinstance(path, str) or not path.lower().endswith(".sldprt"):
            raise ProbeError("Active part must already be saved; this probe never saves or opens documents")
        manager = self.cast(self.call("IModelDoc2.ConfigurationManager", lambda: model.ConfigurationManager), "IConfigurationManager")
        configuration = self.cast(self.call("IConfigurationManager.ActiveConfiguration", lambda: manager.ActiveConfiguration), "IConfiguration")
        name = self.call("IConfiguration.Name", lambda: configuration.Name)
        if not isinstance(name, str) or not name:
            raise ProbeError("Active configuration name could not be read")
        return model, path, name

    def require_identity(self):
        model, path, configuration = self.identity()
        if not same_path(path, self.report["document_path"]) or configuration != self.report["configuration"]:
            raise ProbeError("Active document/configuration changed during the probe")
        self.model = model

    def feature_key(self, feature):
        return (self.call("IFeature.Name", lambda: feature.Name),
                self.call("IFeature.GetTypeName2", feature.GetTypeName2))

    def discover(self):
        found, visited = {}, set()

        def visit(raw):
            chain_seen = set()
            while raw is not None:
                feature = self.cast(raw, "IFeature")
                key = self.feature_key(feature)
                if key in chain_seen:
                    raise ProbeError("Cyclic subfeature traversal")
                chain_seen.add(key)
                if key not in visited:
                    visited.add(key)
                    if len(visited) > 10000:
                        raise ProbeError("Feature traversal exceeded safety limit")
                    if key[1] in ("SheetMetal", "TemplateSheetMetal"):
                        states = self.call("IFeature.IsSuppressed2", lambda: feature.IsSuppressed2(1, None))
                        if not isinstance(states, (list, tuple)) or len(states) != 1 or type(states[0]) is not bool:
                            raise ProbeError(f"{key[0]}: unexpected IsSuppressed2 result")
                        if not states[0]:
                            found[key] = feature
                    child = self.call("IFeature.GetFirstSubFeature", feature.GetFirstSubFeature)
                    visit(child)
                raw = self.call("IFeature.GetNextSubFeature", feature.GetNextSubFeature)

        raw = self.call("IModelDoc2.FirstFeature", self.model.FirstFeature)
        top_seen = set()
        while raw is not None:
            feature = self.cast(raw, "IFeature")
            key = self.feature_key(feature)
            if key in top_seen:
                raise ProbeError("Cyclic top-level feature traversal")
            top_seen.add(key)
            visit(feature)
            raw = self.call("IFeature.GetNextFeature", feature.GetNextFeature)
        extension = self.cast(self.call("IModelDoc2.Extension", lambda: self.model.Extension), "IModelDocExtension")
        template = self.call("IModelDocExtension.GetTemplateSheetMetal", extension.GetTemplateSheetMetal)
        folder_fallback = template is None
        if template is None:
            manager = self.cast(self.call("IModelDoc2.FeatureManager", lambda: self.model.FeatureManager), "IFeatureManager")
            folder = self.call("IFeatureManager.GetSheetMetalFolder", manager.GetSheetMetalFolder)
            if folder is not None:
                folder = self.cast(folder, "ISheetMetalFolder")
                template = self.call("ISheetMetalFolder.GetFeature", folder.GetFeature)
        if template is not None:
            feature = self.cast(template, "IFeature")
            key = self.feature_key(feature)
            if key[1] != "TemplateSheetMetal" and not (folder_fallback and key[1] == "SheetMetal"):
                raise ProbeError(f"Unexpected template feature type: {key[1]}")
            states = self.call("IFeature.IsSuppressed2", lambda: feature.IsSuppressed2(1, None))
            if not isinstance(states, (list, tuple)) or len(states) != 1 or type(states[0]) is not bool:
                raise ProbeError("Unexpected template suppression result")
            if not states[0]:
                found[key] = feature
        return found

    def definition(self, feature):
        return self.cast(self.call("IFeature.GetDefinition", feature.GetDefinition), "ISheetMetalFeatureData")

    def state(self, feature):
        name, kind = self.feature_key(feature)
        data = self.definition(feature)
        allowance = self.cast(self.call("ISheetMetalFeatureData.GetCustomBendAllowance", data.GetCustomBendAllowance), "ICustomBendAllowance")
        allowance_type = self.call("ICustomBendAllowance.Type", lambda: allowance.Type)
        if type(allowance_type) is not int:
            raise ProbeError("Unexpected bend allowance type")
        payload_member = {1: "BendTableFile", 2: "KFactor", 3: "BendAllowance", 4: "BendDeduction"}.get(allowance_type)
        payload = self.call(f"ICustomBendAllowance.{payload_member}", lambda: getattr(allowance, payload_member)) if payload_member else None
        thickness = number(self.call("ISheetMetalFeatureData.Thickness", lambda: data.Thickness), "API Thickness") * 1000
        radius = number(self.call("ISheetMetalFeatureData.BendRadius", lambda: data.BendRadius), "API BendRadius") * 1000
        if thickness <= 0 or radius < 0:
            raise ProbeError("Invalid sheet metal dimensions returned by API")
        if allowance_type in (2, 3, 4):
            payload = number(payload, "API allowance payload")
        if allowance_type == 1 and not isinstance(payload, str):
            raise ProbeError("Unexpected bend table filename")
        return {"feature_name": name, "feature_type": kind, "thickness_mm": thickness,
                "k_factor": payload if allowance_type == 2 else None, "radius_mm": radius,
                "bend_allowance_type": allowance_type,
                "bend_allowance_mm": payload * 1000 if allowance_type == 3 else None,
                "bend_deduction_mm": payload * 1000 if allowance_type == 4 else None,
                "bend_table_file": payload if allowance_type == 1 else None}, data

    def controls(self, data):
        diagnostic = {"gauge_status_code": None, "gauge_status_name": None, "use_gauge_table": None,
                      "gauge_table_file": None, "use_material_parameters": None, "error": None}
        try:
            result = self.call("ISheetMetalFeatureData.GetUseGaugeTable", data.GetUseGaugeTable)
            if (not isinstance(result, tuple) or len(result) != 3 or type(result[0]) is not int):
                raise ProbeError("GetUseGaugeTable must return (status, used, file) from generated wrapper")
            code, used, filename = result
            diagnostic["gauge_status_code"] = code
            diagnostic["gauge_status_name"] = {0: "NoError", 1: "OldArchitecture", 2: "NotEnabledOnTemplate",
                                                3: "InvalidProperty", 4: "UnspecifiedError",
                                                5: "GaugeTablePathNotEmpty"}.get(code, "Unknown")
            if code != 0:
                diagnostic["error"] = f"GetUseGaugeTable returned {code}; OUT values are unavailable"
                return diagnostic
            if type(used) is not bool:
                raise ProbeError("GetUseGaugeTable returned invalid OUT types")
            # The filename OUT is documented as valid only when the table is
            # enabled. NULL BSTR becomes None in pywin32; ignore it when off.
            diagnostic.update(use_gauge_table=used, gauge_table_file=filename if used and isinstance(filename, str) else None)
            if used:
                diagnostic["error"] = "Gauge table controls this feature"
                return diagnostic
            material = self.call("ISheetMetalFeatureData.UseMaterialSheetMetalParameters", lambda: data.UseMaterialSheetMetalParameters)
            if type(material) is not bool:
                raise ProbeError("Unexpected material control result")
            diagnostic.update(use_material_parameters=material)
            if material:
                diagnostic["error"] = "Material sheet metal parameters control this feature"
        except Exception as error:
            diagnostic["error"] = str(error)
        return diagnostic

    def reacquire(self, key):
        self.require_identity()
        candidates = self.discover()
        if key not in candidates:
            raise ProbeError("Selected sheet metal feature disappeared after rebuild")
        return candidates[key]

    def radial_dimension(self, feature):
        key = self.feature_key(feature)
        dimensions = []
        seen = set()
        raw = self.call("IFeature.GetFirstDisplayDimension", feature.GetFirstDisplayDimension)
        for _ in range(1000):
            if raw is None:
                break
            display = self.cast(raw, "IDisplayDimension")
            kind = self.call("IDisplayDimension.Type2", lambda: display.Type2)
            if kind == 5:  # swRadialDimension; diameters deliberately excluded.
                dimension = self.cast(self.call("IDisplayDimension.GetDimension2", lambda: display.GetDimension2(0)), "IDimension")
                raw_owner = self.call("IDimension.GetFeatureOwner", dimension.GetFeatureOwner)
                owner = self.cast(raw_owner, "IFeature") if raw_owner is not None else None
                if owner is not None and self.feature_key(owner) == key:
                    full_name = self.call("IDimension.FullName", lambda: dimension.FullName)
                    if full_name in seen:
                        raise ProbeError("Repeated radial dimension during traversal")
                    seen.add(full_name)
                    dimensions.append(dimension)
            raw = self.call("IFeature.GetNextDisplayDimension", lambda: feature.GetNextDisplayDimension(display))
        else:
            raise ProbeError("Display dimension traversal exceeded safety limit")
        if len(dimensions) > 1:
            raise ProbeError("Multiple root-owned radial dimensions; radius target is ambiguous")
        return dimensions[0] if dimensions else None

    def check_feature_error(self, feature):
        result = self.call("IFeature.GetErrorCode2", feature.GetErrorCode2)
        if (not isinstance(result, tuple) or len(result) != 2 or type(result[0]) is not int
                or type(result[1]) is not bool):
            raise ProbeError("GetErrorCode2 must return (code, is_warning)")
        code, warning = result
        if code and not warning:
            raise ProbeError(f"Feature rebuild error: {code}")
        if code:
            self.report["warnings"].append(f"Feature rebuild warning: {code}")

    def require_radius_dimension(self, feature):
        dimension = self.radial_dimension(feature)
        if dimension is None:
            raise ProbeError("Owned radial dimension disappeared after ModifyDefinition")
        if self.call("IDimension.FullName", lambda: dimension.FullName) != self.radius_dimension_name:
            raise ProbeError("Radius dimension identity changed after ModifyDefinition")
        return dimension

    def write(self, feature, target):
        self.require_identity()
        key = self.feature_key(feature)
        if self.report["radius_method"] == "owned_radial_dimension":
            self.require_radius_dimension(feature)
        data = self.definition(feature)
        accessed = False
        consumed = False
        write_error = None
        try:
            accessed = self.call("ISheetMetalFeatureData.AccessSelections", lambda: data.AccessSelections(self.model, self.binding.null_component))
            if accessed is not True:
                raise ProbeError("AccessSelections returned false")
            allowance = self.cast(self.call("ISheetMetalFeatureData.GetCustomBendAllowance", data.GetCustomBendAllowance), "ICustomBendAllowance")
            kind = target["bend_allowance_type"]
            member = {1: "BendTableFile", 2: "KFactor", 3: "BendAllowance", 4: "BendDeduction"}.get(kind)
            if member is None:
                raise ProbeError("Cannot restore unsupported bend allowance type")
            payload = {1: target["bend_table_file"], 2: target["k_factor"],
                       3: None if target["bend_allowance_mm"] is None else target["bend_allowance_mm"] / 1000,
                       4: None if target["bend_deduction_mm"] is None else target["bend_deduction_mm"] / 1000}[kind]
            self.require_identity()
            self.mutation_attempted = True
            self.call(f"ICustomBendAllowance.{member}=", lambda: setattr(allowance, member, payload))
            self.call("ICustomBendAllowance.Type=", lambda: setattr(allowance, "Type", kind))
            self.call("ISheetMetalFeatureData.SetCustomBendAllowance", lambda: data.SetCustomBendAllowance(allowance))
            if self.report["radius_method"] == "bend_radius_definition":
                self.call("ISheetMetalFeatureData.BendRadius=", lambda: setattr(data, "BendRadius", target["radius_mm"] / 1000))
            if self.call("IFeature.ModifyDefinition", lambda: feature.ModifyDefinition(data, self.model, self.binding.null_component)) is not True:
                raise ProbeError("ModifyDefinition returned false")
            consumed = True
        except Exception as error:
            write_error = error
            raise
        finally:
            # ModifyDefinition releases selection access after a successful
            # commit; otherwise explicitly unwind the rolled-back feature tree.
            if accessed and not consumed:
                try:
                    self.call("ISheetMetalFeatureData.ReleaseSelectionAccess", data.ReleaseSelectionAccess)
                except Exception as release_error:
                    if write_error is None:
                        raise
                    self.report["warnings"].append(f"ReleaseSelectionAccess also failed: {release_error}")
        if self.report["radius_method"] == "owned_radial_dimension":
            # Definition modifications can invalidate previously obtained COM
            # dimensions. Reacquire the owning feature before selecting again.
            fresh = self.reacquire(key)
            dimension = self.require_radius_dimension(fresh)
            self.require_identity()
            result = self.call("IDimension.SetSystemValue3", lambda: dimension.SetSystemValue3(
                target["radius_mm"] / 1000, 1, self.binding.empty_configurations))
            if type(result) is not int or result != 0:
                raise ProbeError(f"SetSystemValue3 failed: {result}")
        self.require_identity()
        if self.call("IModelDoc2.EditRebuild3", self.model.EditRebuild3) is not True:
            raise ProbeError("EditRebuild3 returned false")
        self.check_feature_error(self.reacquire(key))

    @staticmethod
    def states_equal(actual, expected):
        if actual["feature_name"] != expected["feature_name"] or actual["feature_type"] != expected["feature_type"]:
            return False
        if actual["bend_allowance_type"] != expected["bend_allowance_type"]:
            return False
        for key in ("thickness_mm", "radius_mm"):
            if not math.isclose(actual[key], expected[key], rel_tol=1e-9, abs_tol=1e-6):
                return False
        for key in ("k_factor", "bend_allowance_mm", "bend_deduction_mm", "bend_table_file"):
            a, b = actual[key], expected[key]
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
                    return False
            elif a != b:
                return False
        return True

    def run(self, request):
        self.model, path, configuration = self.identity()
        self.report.update(document_path=path, configuration=configuration)
        if request.get("document_path") and not same_path(path, request["document_path"]):
            raise ProbeError("Active document does not match request document_path")
        if request.get("configuration") is not None and configuration != request["configuration"]:
            raise ProbeError("Active configuration does not match the selected configuration; read the part again")
        candidates = self.discover()
        for key, feature in candidates.items():
            item = {"name": key[0], "type": key[1], "suppressed": False, "parent_name": None}
            try:
                state, data = self.state(feature)
                item.update(state=state, controls=self.controls(data))
            except Exception as error:
                item["error"] = str(error)
            self.report["features"].append(item)
        if request.get("feature_name"):
            selection = [key for key in candidates if key[0] == request["feature_name"]]
        else:
            selection = [key for key in candidates if key[1] == "TemplateSheetMetal"]
            if not selection:
                selection = list(candidates)
        if not selection and not candidates and not request.get("feature_name"):
            self.report["status"] = "skipped"
            self.report["warnings"].append("No active sheet metal feature; nothing was changed")
            return
        if len(selection) != 1:
            raise ProbeError("No unique sheet metal target; select an exact feature_name after inspect")
        key = selection[0]
        self.report["feature"] = next(item for item in self.report["features"] if item["name"] == key[0] and item["type"] == key[1])
        before, data = self.state(candidates[key])
        self.report["before"] = before
        if request.get("expected_state") is not None and not self.states_equal(before, request["expected_state"]):
            raise ProbeError("Sheet metal parameters changed since the part was read; read the part again")
        controls = self.controls(data)
        if request["mode"] == "inspect":
            self.report.update(status="inspected", after=before.copy())
            return
        templates = [candidate for candidate in candidates if candidate[1] == "TemplateSheetMetal"]
        sheets = [candidate for candidate in candidates if candidate[1] == "SheetMetal"]
        if templates:
            if len(templates) != 1 or key != templates[0]:
                raise ProbeError("Only the unique TemplateSheetMetal root can be written; child features are inspect-only")
        elif len(sheets) != 1 or key != sheets[0]:
            raise ProbeError("Without a template, only a unique legacy SheetMetal feature can be written")
        matches = [row for row in request["assignments"]
                   if abs(row["thickness_mm"] - before["thickness_mm"]) <= request["tolerance_mm"]]
        if not matches:
            self.report["status"] = "skipped"
            self.report["warnings"].append("No matching thickness assignment; nothing was changed")
            return
        if len(matches) != 1:
            raise ProbeError("Multiple matching thickness assignments")
        writable = (controls["gauge_status_code"] == 0 and controls["use_gauge_table"] is False
                    and controls["use_material_parameters"] is False and controls["error"] is None)
        if not writable:
            if request["mode"] == "verify" and controls["gauge_status_code"] == 2:
                self.report["warnings"].append("GetUseGaugeTable=2 (NotEnabledOnTemplate): writable source unverified; temporary verify only, followed by mandatory baseline restoration")
            else:
                raise ProbeError("Unverified writable source: " + str(controls["error"]))
        if before["bend_allowance_type"] not in (1, 2, 3, 4):
            raise ProbeError("Cannot guarantee rollback of the current bend allowance type")
        if before["bend_allowance_type"] == 2 and not 0 <= before["k_factor"] <= 1:
            raise ProbeError("Original K factor is outside [0,1]; cannot guarantee baseline restoration")
        table_key = {1: "bend_table_file"}.get(before["bend_allowance_type"])
        if table_key and (not before[table_key] or not before[table_key].strip()):
            raise ProbeError("Original bend table path is empty; cannot guarantee baseline restoration")
        assignment = matches[0]
        self.report["assignment"] = assignment
        target = dict(before, k_factor=assignment["k_factor"], radius_mm=assignment["radius_mm"],
                      bend_allowance_type=2, bend_allowance_mm=None, bend_deduction_mm=None, bend_table_file=None)
        self.require_identity()
        current, _ = self.state(candidates[key])
        if not self.states_equal(current, before):
            raise ProbeError("Target state changed before writing")
        dimension = self.radial_dimension(candidates[key])
        self.report["radius_method"] = "owned_radial_dimension" if dimension is not None else "bend_radius_definition"
        if dimension is not None:
            values = self.call("IDimension.GetSystemValue3", lambda: dimension.GetSystemValue3(1, self.binding.empty_configurations))
            if not isinstance(values, (tuple, list)) or len(values) != 1:
                raise ProbeError("Radius dimension must return one value for the active configuration")
            actual_radius_mm = number(values[0], "API radius dimension value") * 1000
            if not math.isclose(actual_radius_mm, before["radius_mm"], rel_tol=0, abs_tol=1e-6):
                raise ProbeError("Owned radial dimension does not match the sheet-metal bend radius; nothing was changed")
            self.radius_dimension_name = self.call("IDimension.FullName", lambda: dimension.FullName)
            if not isinstance(self.radius_dimension_name, str) or not self.radius_dimension_name:
                raise ProbeError("Radius dimension has no stable identity")
        self.check_feature_error(candidates[key])
        self.mutation_attempted = False
        original_error = None
        try:
            self.write(candidates[key], target)
            after, _ = self.state(self.reacquire(key))
            self.report["after"] = after
            if not self.states_equal(after, target):
                raise ProbeError("K/R readback does not match target or thickness changed")
            self.require_identity()
            self.report["status"] = "applied" if request["mode"] == "apply" else "verified"
        except Exception as error:
            original_error = error
            self.report["status"] = "error"
        finally:
            if self.mutation_attempted and (original_error is not None or request["mode"] == "verify"):
                try:
                    self.write(self.reacquire(key), before)
                    restored, _ = self.state(self.reacquire(key))
                    if not self.states_equal(restored, before):
                        raise ProbeError("Restored K/R or thickness could not be verified; DO NOT SAVE THE PART")
                    self.report["rollback"] = {"attempted": True, "verified": True,
                                               "status": "restored_after_verification" if original_error is None else "restored_after_error",
                                               "restored_state": restored, "error": None}
                except Exception as rollback_error:
                    self.report["status"] = "error"
                    self.report["rollback"] = {"attempted": True, "verified": False, "status": "failed",
                                               "restored_state": None, "error": str(rollback_error)}
                    if original_error is None:
                        original_error = ProbeError("Baseline restoration failed; DO NOT SAVE THE PART")
        if original_error is not None:
            raise original_error


def execute(raw, connector=connect):
    report = report_template()
    cleanup = None
    try:
        request = validate_request(raw)
        report["mode"] = request["mode"]
        app, binding, cleanup = connector(Trace(report))
        Probe(app, binding, report).run(request)
    except Exception as error:
        report.update(status="error", error=str(error))
    finally:
        if cleanup is not None:
            try:
                cleanup()
            except Exception as error:
                report["status"] = "error"
                report["error"] = f"{report['error'] + '; ' if report['error'] else ''}COM cleanup failed: {error}"
    return report


def load_request(text):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProbeError(f"Duplicate JSON property: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ProbeError(f"Invalid JSON constant: {value}")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        raw = load_request(Path(args.request).read_text(encoding="utf-8-sig"))
        report = execute(raw)
    except Exception as error:
        report = report_template()
        report["error"] = str(error)
    output = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    exit_code = 2 if report["status"] == "error" else 0
    try:
        destination = Path(args.report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output + "\n", encoding="utf-8")
    except OSError as error:
        report.update(status="error", error=str(error))
        output = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        exit_code = 2
    print(output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
