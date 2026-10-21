using System.Reflection;
using System.Runtime.Loader;
using Microsoft.Win32;

namespace Gokworks.KrProbe;

/// <summary>Use the user's installed SolidWorks interfaces; do not redistribute its DLLs.</summary>
internal static class InstalledInterop
{
    internal static void Register()
    {
        if (OperatingSystem.IsWindows()) AssemblyLoadContext.Default.Resolving += Resolve;
    }

    private static Assembly? Resolve(AssemblyLoadContext context, AssemblyName name)
    {
        if (name.Name is not ("SolidWorks.Interop.sldworks" or "SolidWorks.Interop.swconst")) return null;
        foreach (var folder in Directories())
        {
            string path = Path.Combine(folder, name.Name + ".dll");
            if (File.Exists(path)) return context.LoadFromAssemblyPath(Path.GetFullPath(path));
        }
        return null;
    }

    private static IEnumerable<string> Directories()
    {
        var paths = new List<string>();
        string? configured = Environment.GetEnvironmentVariable("GOKWORKS_KR_INTEROP_DIR");
        if (!string.IsNullOrWhiteSpace(configured)) paths.Add(configured);
        // LocalServer32 identifies the actual registered SolidWorks installation.
        // The registry text is parsed as a path, never executed as a command.
        try
        {
            using var prog = Registry.ClassesRoot.OpenSubKey(@"SldWorks.Application\CLSID");
            string? clsid = prog?.GetValue(null) as string;
            if (!string.IsNullOrWhiteSpace(clsid))
            {
                using var server = Registry.ClassesRoot.OpenSubKey(@"CLSID\" + clsid + @"\LocalServer32");
                string? command = server?.GetValue(null) as string;
                if (!string.IsNullOrWhiteSpace(command))
                {
                    string expanded = Environment.ExpandEnvironmentVariables(command.Trim());
                    int end = expanded.IndexOf("SLDWORKS.exe", StringComparison.OrdinalIgnoreCase);
                    if (end >= 0)
                    {
                        string executable = expanded[..(end + "SLDWORKS.exe".Length)].Trim('"');
                        string? installation = Path.GetDirectoryName(executable);
                        if (installation is not null) paths.Add(Path.Combine(installation, "api", "redist"));
                    }
                }
            }
        }
        catch (System.Security.SecurityException) { }
        catch (UnauthorizedAccessException) { }
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        paths.Add(Path.Combine(programFiles, "SOLIDWORKS Corp", "SOLIDWORKS", "api", "redist"));
        return paths.Distinct(StringComparer.OrdinalIgnoreCase);
    }
}
