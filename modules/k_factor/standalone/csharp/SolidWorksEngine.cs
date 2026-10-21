using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace Gokworks.KrProbe;

/// <summary>Typed COM experiment: one definition in the active part/configuration. Never saves.</summary>
public sealed class SolidWorksEngine
{
    private readonly Report report;
    private ISldWorks? app;
    private IModelDoc2? model;
    private string path = "";
    private string configuration = "";
    private readonly List<FeatureHandle> handles = [];

    private sealed record FeatureHandle(IFeature Feature, FeatureInfo Info);

    public SolidWorksEngine(Report report) => this.report = report;

    public Report Execute(Request request)
    {
        request.Validate();
        if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("Native SolidWorks checks require Windows and a running SolidWorks instance.");
        if (Thread.CurrentThread.GetApartmentState() != ApartmentState.STA)
            throw new InvalidOperationException("SolidWorks probe must execute on an STA thread.");
        app = Trace("ROT.GetActiveObject", NativeConnection.Attach);
        model = Trace("SolidWorks.IActiveDoc2", () => (IModelDoc2?)app.IActiveDoc2)
            ?? throw new InvalidOperationException("No active document in the running SolidWorks instance.");
        if (Trace("Model.GetType", () => model.GetType()) != (int)swDocumentTypes_e.swDocPART)
            throw new InvalidOperationException("Activate a saved .SLDPRT in its own window; assemblies are not modified by this isolated probe.");
        path = Trace("Model.GetPathName", () => model.GetPathName());
        if (string.IsNullOrWhiteSpace(path) || !path.EndsWith(".sldprt", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("The active part must have an existing .SLDPRT path.");
        if (request.DocumentPath is not null && !SamePath(path, request.DocumentPath))
            throw new InvalidOperationException("document_path does not match the active SolidWorks part. No file was opened or changed.");
        configuration = Trace("ConfigurationManager.ActiveConfiguration.Name", () => model.ConfigurationManager.ActiveConfiguration.Name);
        report.DocumentPath = path;
        report.Configuration = configuration;
        if (request.Configuration is not null && request.Configuration != configuration)
            throw new InvalidOperationException("The active configuration does not match the selected configuration. Read the part again before writing.");
        Discover();
        report.Features = handles.Select(x => x.Info).ToList();
        if (handles.Count == 0)
        {
            report.Status = "skipped";
            report.Warnings.Add("No unsuppressed SheetMetal or TemplateSheetMetal feature was found; this part was not changed.");
            return report;
        }
        var selected = Select(request.FeatureName, request.Mode);
        report.Feature = selected.Info;
        report.Before = selected.Info.State ?? throw new InvalidOperationException($"Selected feature cannot be read: {selected.Info.Error}");
        AssertIdentity();
        if (request.ExpectedState is not null)
            AssertEquivalent(request.ExpectedState, report.Before, "Sheet metal parameters changed since the part was read; read the part again");
        if (request.Mode == "inspect")
        {
            report.After = report.Before;
            report.Status = "inspected";
            return report;
        }
        report.Assignment = request.Match(report.Before.ThicknessMm);
        if (report.Assignment is null)
        {
            report.Status = "skipped";
            report.Warnings.Add("No assignment matches the selected feature's actual thickness; nothing was changed.");
            return report;
        }
        ValidateBaseline(report.Before);
        CheckFeatureError(selected.Feature, "Before.GetErrorCode2");
        var baseline = report.Before;
        var target = new FeatureState(baseline.FeatureName, baseline.FeatureType, baseline.ThicknessMm,
            report.Assignment.KFactor, report.Assignment.RadiusMm, (int)swBendAllowanceTypes_e.swBendAllowanceKFactor);
        AssertEquivalent(baseline, ReadState(Fresh(baseline), "Before.Write"), "The selected feature changed before writing");
        report.RadiusMethod = "bend_radius_definition";
        bool mutationAttempted = false;
        try
        {
            Write(target, "Write", ref mutationAttempted);
            RebuildAndCheck(target, "Target");
            report.After = ReadState(Fresh(target), "Target.ReadBack");
            AssertEquivalent(target, report.After, "Requested K/R values were not preserved after rebuild");
            AssertIdentity();
            if (request.Mode == "verify")
            {
                Restore(baseline, "restored_after_verification");
                if (report.Rollback?.Verified != true)
                    throw new InvalidOperationException("The requested values were verified, but the baseline could not be restored and verified. Do not save the part.");
                report.Status = "verified";
            }
            else report.Status = "applied";
        }
        catch (Exception error)
        {
            report.Status = "error";
            report.Error = Describe(error);
            if (mutationAttempted && report.Rollback?.Verified != true)
                Restore(baseline, "restored_after_error");
            if (report.Rollback is { Attempted: true, Verified: false })
                report.Error += " Baseline restoration could not be verified. Do not save the part.";
        }
        return report;
    }

    private void Discover()
    {
        var visited = new HashSet<nint>();
        int visitedCount = 0;
        void Walk(IFeature? feature, string? parent, bool subfeatures)
        {
            while (feature is not null)
            {
                if (++visitedCount > 20000) throw new InvalidOperationException("Feature traversal exceeded the safety limit.");
                nint identity = Marshal.GetIUnknownForObject(feature);
                bool isNew;
                try { isNew = visited.Add(identity); }
                finally { Marshal.Release(identity); }
                if (isNew)
                {
                    var name = Trace("Feature.Name", () => feature.Name);
                    var kind = Trace($"{name}.GetTypeName2", () => feature.GetTypeName2());
                    bool sheetMetal = kind is "SheetMetal" or "TemplateSheetMetal";
                    // History/UI/body folders need not expose configuration
                    // suppression. Only a real sheet-metal candidate requires it.
                    bool suppressed = sheetMetal && IsSuppressed(feature);
                    if (sheetMetal && !suppressed) Add(feature, name, kind, parent);
                    if (!suppressed)
                        Walk(Trace($"{name}.GetFirstSubFeature", () => feature.GetFirstSubFeature() as IFeature), name, true);
                }
                feature = subfeatures
                    ? Trace("Feature.GetNextSubFeature", () => feature.GetNextSubFeature() as IFeature)
                    : Trace("Feature.GetNextFeature", () => feature.GetNextFeature() as IFeature);
            }
        }
        Walk(Trace("Model.FirstFeature", () => model!.FirstFeature() as IFeature), null, false);
        object? rawTemplate = Trace("Model.Extension.GetTemplateSheetMetal", () => model!.Extension.GetTemplateSheetMetal());
        var template = rawTemplate is null ? null : rawTemplate as IFeature
            ?? throw new InvalidOperationException("GetTemplateSheetMetal returned a non-IFeature object.");
        bool folderFallback = template is null;
        if (template is null)
        {
            object? rawFolder = Trace("Model.FeatureManager.GetSheetMetalFolder", () => model!.FeatureManager.GetSheetMetalFolder());
            var folder = rawFolder is null ? null : rawFolder as ISheetMetalFolder
                ?? throw new InvalidOperationException("GetSheetMetalFolder returned a non-ISheetMetalFolder object.");
            if (folder is not null)
                template = Trace("SheetMetalFolder.GetFeature", () => folder.GetFeature() as IFeature);
        }
        if (template is not null)
        {
            var name = template.Name;
            var kind = template.GetTypeName2();
            if (kind != "TemplateSheetMetal" && (!folderFallback || kind != "SheetMetal"))
                throw new InvalidOperationException($"GetTemplateSheetMetal returned unexpected type {kind}; selection is ambiguous.");
            if (!IsSuppressed(template) && !handles.Any(x => x.Info.Name == name && x.Info.Type == kind))
                Add(template, name, kind, null);
        }
    }

    private void Add(IFeature feature, string name, string kind, string? parent)
    {
        var info = new FeatureInfo { Name = name, Type = kind, Suppressed = false, ParentName = parent };
        try { info.State = ReadState(feature, $"Inspect.{name}"); }
        catch (Exception ex) { info.Error = Describe(ex); }
        handles.Add(new FeatureHandle(feature, info));
    }

    private bool IsSuppressed(IFeature feature)
    {
        var value = Trace($"{feature.Name}.IsSuppressed2", () => feature.IsSuppressed2((int)swInConfigurationOpts_e.swThisConfiguration, null!));
        return value switch
        {
            bool flag => flag,
            Array flags when flags.Length == 1 && flags.GetValue(flags.GetLowerBound(0)) is bool flag => flag,
            _ => throw new InvalidOperationException($"Cannot establish suppression state of {feature.Name} in the active configuration.")
        };
    }

    private FeatureHandle Select(string? name, string mode)
    {
        var templates = handles.Where(x => x.Info.Type == "TemplateSheetMetal").ToList();
        if (templates.Count > 1) throw new InvalidOperationException("More than one active template parent exists; the part will not be modified.");
        if (name is not null)
        {
            var selected = handles.Where(x => x.Info.Name == name).ToList();
            if (selected.Count != 1) throw new InvalidOperationException("feature_name must match exactly one unsuppressed sheet-metal feature.");
            if (mode != "inspect" && (templates.Count == 1 && selected[0] != templates[0] ||
                templates.Count == 0 && handles.Count != 1))
                throw new InvalidOperationException("Writing is restricted to the unique template parent, or the sole legacy SheetMetal definition. Child overrides are not modified by this experiment.");
            return selected[0];
        }
        if (templates.Count == 1) return templates[0];
        var sheets = handles.Where(x => x.Info.Type == "SheetMetal").ToList();
        if (sheets.Count != 1)
            throw new InvalidOperationException("More than one SheetMetal feature exists without a unique template parent; provide an exact feature_name.");
        return sheets[0];
    }

    private FeatureState ReadState(IFeature feature, string prefix)
    {
        var data = Definition(feature, prefix);
        var allowance = Trace(prefix + ".GetCustomBendAllowance", () => data.GetCustomBendAllowance())
            ?? throw new InvalidOperationException("GetCustomBendAllowance returned null.");
        int kind = Trace(prefix + ".Allowance.Type", () => allowance.Type);
        var result = new FeatureState(feature.Name, feature.GetTypeName2(),
            Trace(prefix + ".Thickness", () => data.Thickness) * 1000,
            kind == 2 ? Trace(prefix + ".Allowance.KFactor", () => allowance.KFactor) : null,
            Trace(prefix + ".BendRadius", () => data.BendRadius) * 1000, kind)
        {
            BendAllowanceMm = kind == 3 ? Trace(prefix + ".Allowance.BendAllowance", () => allowance.BendAllowance) * 1000 : null,
            BendDeductionMm = kind == 4 ? Trace(prefix + ".Allowance.BendDeduction", () => allowance.BendDeduction) * 1000 : null,
            BendTableFile = kind == 1 ? Trace(prefix + ".Allowance.BendTableFile", () => allowance.BendTableFile) : null
        };
        if (!double.IsFinite(result.ThicknessMm) || result.ThicknessMm <= 0 ||
            !double.IsFinite(result.RadiusMm) || result.RadiusMm < 0 ||
            (result.KFactor.HasValue && !double.IsFinite(result.KFactor.Value)))
            throw new InvalidOperationException("SolidWorks returned non-finite or invalid sheet-metal values.");
        return result;
    }

    private static void ValidateBaseline(FeatureState state)
    {
        // Type 5 is not exposed by the pinned, strongly typed interop contract.
        // Inspection can report it, but guessing a payload would break rollback.
        if (state.BendAllowanceType is < 1 or > 4)
            throw new InvalidOperationException("The bend allowance type cannot be restored safely.");
        if (state.BendAllowanceType == 2 && (!state.KFactor.HasValue || state.KFactor < 0 || state.KFactor > 1))
            throw new InvalidOperationException("The original K factor is outside [0,1].");
        if (state.BendAllowanceType == 3 && (state.BendAllowanceMm is null || !double.IsFinite(state.BendAllowanceMm.Value)))
            throw new InvalidOperationException("The original bend allowance cannot be restored safely.");
        if (state.BendAllowanceType == 4 && (state.BendDeductionMm is null || !double.IsFinite(state.BendDeductionMm.Value)))
            throw new InvalidOperationException("The original bend deduction cannot be restored safely.");
        if (state.BendAllowanceType == 1 && string.IsNullOrWhiteSpace(state.BendTableFile))
            throw new InvalidOperationException("The original bend-table path cannot be restored safely.");
    }

    private void Write(FeatureState state, string prefix, ref bool mutationAttempted)
    {
        AssertIdentity();
        var feature = Fresh(state);
        var data = Definition(feature, prefix);
        bool accessed = false;
        bool committed = false;
        Exception? writeFailure = null;
        try
        {
            accessed = Trace(prefix + ".AccessSelections", () => data.AccessSelections(model!, null!));
            if (!accessed) throw new InvalidOperationException("AccessSelections returned false.");
            var allowance = Trace(prefix + ".GetCustomBendAllowance", () => data.GetCustomBendAllowance())
                ?? throw new InvalidOperationException("GetCustomBendAllowance returned null.");
            AssertIdentity();
            mutationAttempted = true;
            // Active value setters may change Type. Finalize Type after writing the payload.
            Trace(prefix + ".SetAllowancePayload", () =>
            {
                switch (state.BendAllowanceType)
                {
                    case 1: allowance.BendTableFile = state.BendTableFile; break;
                    case 2: allowance.KFactor = state.KFactor!.Value; break;
                    case 3: allowance.BendAllowance = state.BendAllowanceMm!.Value / 1000; break;
                    case 4: allowance.BendDeduction = state.BendDeductionMm!.Value / 1000; break;
                    default: throw new InvalidOperationException("Unsupported bend allowance type.");
                }
                allowance.Type = state.BendAllowanceType;
            });
            Trace(prefix + ".SetCustomBendAllowance", () => data.SetCustomBendAllowance(allowance));
            Trace(prefix + ".BendRadius.set", () => data.BendRadius = state.RadiusMm / 1000);
            committed = Trace(prefix + ".ModifyDefinition", () => feature.ModifyDefinition(data, model!, null!));
            if (!committed) throw new InvalidOperationException("ModifyDefinition returned false.");
        }
        catch (Exception ex)
        {
            writeFailure = ex;
            throw;
        }
        finally
        {
            if (accessed && !committed)
            {
                try { Trace(prefix + ".ReleaseSelectionAccess", () => data.ReleaseSelectionAccess()); }
                catch (Exception releaseError) when (writeFailure is not null)
                {
                    // Keep the original failing API operation; cleanup failure is also in calls.
                    report.Warnings.Add("ReleaseSelectionAccess also failed: " + Describe(releaseError));
                }
            }
        }
    }

    private void RebuildAndCheck(FeatureState state, string prefix)
    {
        AssertIdentity();
        if (!Trace(prefix + ".EditRebuild3", () => model!.EditRebuild3()))
            throw new InvalidOperationException("EditRebuild3 returned false.");
        AssertIdentity();
        CheckFeatureError(Fresh(state), prefix + ".GetErrorCode2");
    }

    private void CheckFeatureError(IFeature feature, string operation)
    {
        bool warning = false;
        int code = Trace(operation, () => feature.GetErrorCode2(out warning));
        if (code != 0 && !warning) throw new InvalidOperationException($"The selected feature reports rebuild error {code}.");
        if (code != 0) report.Warnings.Add($"The selected feature reports warning {code} ({operation}).");
    }

    private void Restore(FeatureState baseline, string status)
    {
        var rollback = report.Rollback = new RollbackReport { Attempted = true, Status = "failed" };
        try
        {
            bool mutation = false;
            Write(baseline, "Rollback", ref mutation);
            RebuildAndCheck(baseline, "Rollback");
            rollback.RestoredState = ReadState(Fresh(baseline), "Rollback.ReadBack");
            AssertEquivalent(baseline, rollback.RestoredState, "Restoring the original definition did not preserve its complete active allowance payload and geometry");
            AssertIdentity();
            rollback.Verified = true;
            rollback.Status = status;
        }
        catch (Exception ex) { rollback.Error = Describe(ex); }
    }

    private static void AssertEquivalent(FeatureState expected, FeatureState actual, string message)
    {
        bool close(double a, double b) => Math.Abs(a - b) <= 0.000001;
        bool payload = expected.BendAllowanceType switch
        {
            1 => string.Equals(expected.BendTableFile, actual.BendTableFile, StringComparison.OrdinalIgnoreCase),
            2 => expected.KFactor.HasValue && actual.KFactor.HasValue && Math.Abs(expected.KFactor.Value - actual.KFactor.Value) <= 0.000000001,
            3 => expected.BendAllowanceMm.HasValue && actual.BendAllowanceMm.HasValue && close(expected.BendAllowanceMm.Value, actual.BendAllowanceMm.Value),
            4 => expected.BendDeductionMm.HasValue && actual.BendDeductionMm.HasValue && close(expected.BendDeductionMm.Value, actual.BendDeductionMm.Value),
            _ => false
        };
        if (expected.FeatureName != actual.FeatureName || expected.FeatureType != actual.FeatureType ||
            !close(expected.ThicknessMm, actual.ThicknessMm) || !close(expected.RadiusMm, actual.RadiusMm) ||
            expected.BendAllowanceType != actual.BendAllowanceType || !payload)
            throw new InvalidOperationException(message + ".");
    }

    private ISheetMetalFeatureData Definition(IFeature feature, string prefix) =>
        Trace(prefix + ".GetDefinition", () => feature.GetDefinition() as ISheetMetalFeatureData)
        ?? throw new InvalidOperationException($"{feature.Name} does not expose ISheetMetalFeatureData.");

    private IFeature Fresh(FeatureState state)
    {
        AssertIdentity();
        var feature = Trace("Model.FeatureByName", () => ((IPartDoc)model!).FeatureByName(state.FeatureName) as IFeature);
        if (feature is null || feature.GetTypeName2() != state.FeatureType || IsSuppressed(feature))
            throw new InvalidOperationException("The selected sheet-metal feature could not be reacquired unambiguously.");
        return feature;
    }

    private void AssertIdentity()
    {
        var active = Trace("Identity.IActiveDoc2", () => (IModelDoc2?)app!.IActiveDoc2);
        if (active is null || active.GetType() != (int)swDocumentTypes_e.swDocPART ||
            !SamePath(path, active.GetPathName()) || active.ConfigurationManager.ActiveConfiguration.Name != configuration)
            throw new InvalidOperationException("The active part or configuration changed; no further writes are allowed.");
    }

    private static bool SamePath(string first, string second) => string.Equals(Path.GetFullPath(first), Path.GetFullPath(second), StringComparison.OrdinalIgnoreCase);
    public static string Describe(Exception ex) => ex is COMException com ? $"{com.Message} (HRESULT 0x{com.HResult:X8})" : ex.Message;

    private T Trace<T>(string operation, Func<T> action)
    {
        try
        {
            T result = action();
            report.Calls.Add(new CallTrace(operation, true, result is null ? "null" : result is string or bool or int or double ? result.ToString() : "typed COM result"));
            return result;
        }
        catch (Exception ex)
        {
            report.Calls.Add(new CallTrace(operation, false, Error: Describe(ex), Hresult: ex.HResult));
            throw;
        }
    }
    private void Trace(string operation, Action action) => Trace(operation, () => { action(); return true; });
}

internal static class NativeConnection
{
    [DllImport("ole32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    private static extern void CLSIDFromProgID(string progId, out Guid classId);
    [DllImport("oleaut32.dll", PreserveSig = false)]
    private static extern void GetActiveObject(ref Guid classId, nint reserved, [MarshalAs(UnmanagedType.IUnknown)] out object instance);

    internal static ISldWorks Attach()
    {
        CLSIDFromProgID("SldWorks.Application", out Guid classId);
        GetActiveObject(ref classId, 0, out object instance);
        return instance as ISldWorks ?? throw new InvalidOperationException("The running instance does not expose ISldWorks.");
    }
}
