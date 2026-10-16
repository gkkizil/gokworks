using System.Text;
using System.Text.Json;

namespace Gokworks.KrProbe;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        InstalledInterop.Register();
        var report = new Report();
        string? reportPath = null;
        try
        {
            if (args.Length == 1 && args[0] == "--self-test") return SelfTest.Run();
            string? requestPath = null;
            for (int i = 0; i < args.Length; i++)
            {
                if (i + 1 >= args.Length) throw new ArgumentException("Usage: --request FILE --report FILE, or --self-test");
                string value = args[++i];
                switch (args[i - 1])
                {
                    case "--request" when requestPath is null: requestPath = value; break;
                    case "--report" when reportPath is null: reportPath = value; break;
                    default: throw new ArgumentException("Unknown or duplicate argument. Usage: --request FILE --report FILE");
                }
            }
            if (requestPath is null || reportPath is null)
                throw new ArgumentException("Both --request FILE and --report FILE are required.");
            var request = JsonContract.Read(File.ReadAllText(requestPath, Encoding.UTF8));
            report.Mode = request.Mode;
            // The separate method keeps the pure self-test free of COM type loading on Linux.
            RunNative(request, report);
        }
        catch (Exception ex)
        {
            report.Status = "error";
            report.Error = ex.Message;
        }
        if (reportPath is not null)
        {
            try
            {
                var target = Path.GetFullPath(reportPath);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                var temporary = target + "." + Guid.NewGuid().ToString("N") + ".tmp";
                File.WriteAllText(temporary, JsonSerializer.Serialize(report, JsonContract.Options) + Environment.NewLine, new UTF8Encoding(false));
                File.Move(temporary, target, true);
            }
            catch (Exception ex)
            {
                report.Status = "error";
                report.Error = (report.Error is null ? "" : report.Error + " ") + "Report file could not be written: " + ex.Message;
            }
        }
        Console.WriteLine(JsonSerializer.Serialize(report, JsonContract.Options));
        return report.Status is "inspected" or "applied" or "verified" or "skipped" ? 0 : 2;
    }

    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static void RunNative(Request request, Report report) => new SolidWorksEngine(report).Execute(request);
}

internal static class SelfTest
{
    internal static int Run()
    {
        int checks = 0;
        void Check(bool condition, string name)
        {
            if (!condition) throw new InvalidOperationException("Self-test failed: " + name);
            checks++;
        }
        void Reject(string json, string name)
        {
            try { JsonContract.Read(json); }
            catch (Exception ex) when (ex is ArgumentException or JsonException) { checks++; return; }
            throw new InvalidOperationException("Self-test accepted invalid request: " + name);
        }
        try
        {
            var request = JsonContract.Read("""{"schema_version":1,"mode":"verify","assignments":[{"thickness_mm":1.5,"k_factor":0.274,"radius_mm":1.5},{"thickness_mm":2,"k_factor":0.33,"radius_mm":2}]}""");
            Check(request.Match(1.5)?.KFactor == 0.274, "actual thickness mapping");
            Check(request.Match(3) is null, "unmatched thickness skips");
            Check(request.Match(2.005)?.RadiusMm == 2, "matching tolerance");
            Check(JsonContract.Read("""{"schema_version":1,"mode":"inspect"}""").Assignments.Count == 0, "inspect needs no assignment");
            Reject("""{"schema_version":2}""", "unsupported schema");
            Reject("""{"schema_version":1,"schema_version":1}""", "duplicate property");
            Reject("""{"schema_version":1,"unexpected":true}""", "unknown property");
            Reject("""{"schema_version":1,"mode":"apply","assignments":[]}""", "empty apply");
            Reject("""{"schema_version":1,"mode":"verify","assignments":[{"thickness_mm":2,"radius_mm":1}]}""", "missing K");
            Reject("""{"schema_version":1,"tolerance_mm":0}""", "zero tolerance");
            Reject("""{"schema_version":1,"assignments":[{"thickness_mm":2,"k_factor":1.1,"radius_mm":1}]}""", "invalid K");
            Reject("""{"schema_version":1,"assignments":[{"thickness_mm":2,"k_factor":0.3,"radius_mm":-1}]}""", "negative R");
            Reject("""{"schema_version":1,"assignments":[{"thickness_mm":2,"k_factor":0.3,"radius_mm":1},{"thickness_mm":2.015,"k_factor":0.4,"radius_mm":2}]}""", "overlapping matching intervals");
            Reject("""{"schema_version":1,"assignments":null}""", "null assignment array");
            Reject("""{"schema_version":1,"mode":null}""", "null mode");
            var report = new Report { Status = "inspected" };
            using var output = JsonDocument.Parse(JsonSerializer.Serialize(report, JsonContract.Options));
            Check(output.RootElement.GetProperty("engine").GetString() == "csharp", "report engine");
            Check(output.RootElement.GetProperty("schema_version").GetInt32() == 1, "report schema");
            Check(output.RootElement.GetProperty("files_saved").GetBoolean() == false, "never save");
            Console.WriteLine(JsonSerializer.Serialize(new { status = "passed", engine = "csharp", checks, native_solidworks_tested = false }, JsonContract.Options));
            return 0;
        }
        catch (Exception ex)
        {
            Console.WriteLine(JsonSerializer.Serialize(new { status = "error", engine = "csharp", checks, error = ex.Message }, JsonContract.Options));
            return 2;
        }
    }
}
