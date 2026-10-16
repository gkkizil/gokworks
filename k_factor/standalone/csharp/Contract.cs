using System.Text.Json;
using System.Text.Json.Serialization;

namespace Gokworks.KrProbe;

public sealed record Assignment([property: JsonRequired] double ThicknessMm,
    [property: JsonRequired] double KFactor, [property: JsonRequired] double RadiusMm);

public sealed class Request
{
    public int SchemaVersion { get; init; }
    public string Mode { get; init; } = "inspect";
    public string? DocumentPath { get; init; }
    public string? FeatureName { get; init; }
    public List<Assignment> Assignments { get; init; } = [];
    public double ToleranceMm { get; init; } = 0.01;

    public void Validate()
    {
        if (SchemaVersion != 1) throw new ArgumentException("schema_version must be 1.");
        if (Mode is not ("inspect" or "apply" or "verify")) throw new ArgumentException("mode must be inspect, apply or verify.");
        if (!double.IsFinite(ToleranceMm) || ToleranceMm <= 0)
            throw new ArgumentException("tolerance_mm must be finite and positive.");
        if (DocumentPath is not null && (string.IsNullOrWhiteSpace(DocumentPath) || !DocumentPath.EndsWith(".sldprt", StringComparison.OrdinalIgnoreCase)))
            throw new ArgumentException("document_path must identify a saved .SLDPRT file.");
        if (FeatureName is not null && string.IsNullOrWhiteSpace(FeatureName))
            throw new ArgumentException("feature_name cannot be empty.");
        if (Assignments is null) throw new ArgumentException("assignments must be an array.");
        foreach (var row in Assignments)
        {
            if (row is null || !double.IsFinite(row.ThicknessMm) || row.ThicknessMm <= 0 ||
                !double.IsFinite(row.KFactor) || row.KFactor < 0 || row.KFactor > 1 ||
                !double.IsFinite(row.RadiusMm) || row.RadiusMm < 0)
                throw new ArgumentException("Each assignment needs finite positive thickness_mm, k_factor in [0,1], and radius_mm >= 0.");
        }
        // Reject overlapping matching intervals rather than choosing a row by order.
        for (int i = 0; i < Assignments.Count; i++)
            for (int j = i + 1; j < Assignments.Count; j++)
                if (Math.Abs(Assignments[i].ThicknessMm - Assignments[j].ThicknessMm) <= 2 * ToleranceMm)
                    throw new ArgumentException("Assignment thickness matching intervals overlap; provide one row for each thickness.");
        if (Mode != "inspect" && Assignments.Count == 0)
            throw new ArgumentException("apply and verify require at least one assignment.");
    }

    public Assignment? Match(double actualThicknessMm)
    {
        if (!double.IsFinite(actualThicknessMm) || actualThicknessMm <= 0)
            throw new InvalidOperationException("The selected feature returned an invalid thickness.");
        var matches = Assignments.Where(x => Math.Abs(x.ThicknessMm - actualThicknessMm) <= ToleranceMm).ToList();
        if (matches.Count > 1) throw new InvalidOperationException("More than one assignment matches the actual thickness.");
        return matches.SingleOrDefault();
    }
}

public sealed record FeatureState(string FeatureName, string FeatureType, double ThicknessMm,
    double? KFactor, double RadiusMm, int BendAllowanceType)
{
    public double? BendAllowanceMm { get; init; }
    public double? BendDeductionMm { get; init; }
    public string? BendTableFile { get; init; }
}

public sealed class ControlState
{
    public int? GaugeStatusCode { get; set; }
    public string? GaugeStatusName { get; set; }
    public bool? UseGaugeTable { get; set; }
    public string? GaugeTableFile { get; set; }
    public bool? UseMaterialParameters { get; set; }
    public string? Error { get; set; }
    [JsonIgnore] public bool Writable => GaugeStatusCode == 0 && UseGaugeTable == false && UseMaterialParameters == false && Error is null;
}

public sealed class FeatureInfo
{
    public string Name { get; init; } = "";
    public string Type { get; init; } = "";
    public bool Suppressed { get; init; }
    public string? ParentName { get; init; }
    public FeatureState? State { get; set; }
    public ControlState? Controls { get; set; }
    public string? Error { get; set; }
}

public sealed record CallTrace(string Operation, bool Success, string? Detail = null, string? Error = null, int? Hresult = null);
public sealed class RollbackReport
{
    public bool Attempted { get; set; }
    public bool Verified { get; set; }
    public string? Status { get; set; }
    public FeatureState? RestoredState { get; set; }
    public string? Error { get; set; }
}

public sealed class Report
{
    public int SchemaVersion { get; init; } = 1;
    public string Engine { get; init; } = "csharp";
    public string Status { get; set; } = "error";
    public string? Mode { get; set; }
    public string Scope { get; init; } = "active_configuration_selected_sheetmetal_definition";
    public bool FilesSaved { get; init; } = false;
    public string? DocumentPath { get; set; }
    public string? Configuration { get; set; }
    public FeatureInfo? Feature { get; set; }
    public Assignment? Assignment { get; set; }
    public FeatureState? Before { get; set; }
    public FeatureState? After { get; set; }
    public string? RadiusMethod { get; set; }
    public RollbackReport? Rollback { get; set; }
    public List<FeatureInfo> Features { get; set; } = [];
    public List<CallTrace> Calls { get; } = [];
    public List<string> Warnings { get; } = [];
    public string? Error { get; set; }
}

public static class JsonContract
{
    public static JsonSerializerOptions Options { get; } = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = false,
        WriteIndented = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow
    };

    public static Request Read(string text)
    {
        // System.Text.Json normally accepts duplicate property names; reject an ambiguous request.
        using var doc = JsonDocument.Parse(text);
        RejectDuplicateKeys(doc.RootElement);
        var request = JsonSerializer.Deserialize<Request>(text, Options) ?? throw new ArgumentException("Request cannot be null.");
        request.Validate();
        return request;
    }

    private static void RejectDuplicateKeys(JsonElement node)
    {
        if (node.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var item in node.EnumerateObject())
            {
                if (!names.Add(item.Name)) throw new ArgumentException($"Duplicate JSON property: {item.Name}");
                RejectDuplicateKeys(item.Value);
            }
        }
        else if (node.ValueKind == JsonValueKind.Array)
            foreach (var item in node.EnumerateArray()) RejectDuplicateKeys(item);
    }
}
