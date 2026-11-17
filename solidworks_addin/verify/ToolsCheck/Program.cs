using System;
using System.IO;
using System.Linq;
using Gokworks.SolidWorksAddin;

static class Program
{
    static int failures;
    static void Check(bool ok, string what) { if (!ok) { failures++; Console.WriteLine("FAIL " + what); } }

    static int Main()
    {
        var drawing = Tools.All.First(t => t.Key == "automatic_drawing");
        var main = Tools.All.First(t => t.Key == "");
        var nesting = Tools.All.First(t => t.Key == "nesting");
        Check(Tools.Arguments(drawing) == "--open automatic_drawing --active", "active arguments");
        Check(Tools.Arguments(nesting) == "--open nesting", "plain arguments");
        Check(Tools.Arguments(main) == "", "main window has no arguments");
        Check(Tools.Accepts(drawing, 1) && Tools.Accepts(drawing, 2) && !Tools.Accepts(drawing, 3) && !Tools.Accepts(drawing, 0), "part/assembly tool");
        var stack = Tools.All.First(t => t.Key == "tolerance_stack");
        Check(Tools.Accepts(stack, 3) && !Tools.Accepts(stack, 1), "drawing tool");
        Check(Tools.Accepts(nesting, 0), "no-document tool");
        Check(Tools.All.Select(t => t.Key).Distinct().Count() == Tools.All.Count, "unique keys");
        Check(Tools.All.Count == 11, "11 commands = Run0..Run10");

        string folder = Path.Combine(Path.GetTempPath(), "gokworks-addin-check-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(folder, "addin"));
        string exe = Path.Combine(folder, "GOKWORKS.exe"); File.WriteAllText(exe, "");
        Environment.SetEnvironmentVariable("GOKWORKS_EXE", exe);
        var info = Tools.StartInfo(drawing, Path.Combine(folder, "addin"));
        Check(info.FileName == exe && info.Arguments == "--open automatic_drawing --active" && !info.UseShellExecute
              && info.WorkingDirectory == folder, "start info from GOKWORKS_EXE");
        Environment.SetEnvironmentVariable("GOKWORKS_EXE", Path.Combine(folder, "missing.exe"));
        try { Tools.StartInfo(drawing, folder); Check(false, "missing exe must throw"); }
        catch (FileNotFoundException error) { Check(error.Message.Contains("GOKWORKS.exe bulunamadı"), "clear message"); }
        Directory.Delete(folder, true);
        Console.WriteLine(failures == 0 ? "ToolsCheck OK" : $"{failures} failure(s)");
        return failures == 0 ? 0 : 1;
    }
}
