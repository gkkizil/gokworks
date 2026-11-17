// GOKWORKS commands shown in SolidWorks and how they start GOKWORKS.
// The tool keys and "active" flags must match gui_qt/app.py MODULES and
// gui_qt/remote.py ACTIVE_ACTIONS (checked by tests/test_solidworks_addin.py).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using Microsoft.Win32;

namespace Gokworks.SolidWorksAddin
{
    /// <summary>Document kinds a command needs open and active in SolidWorks.</summary>
    [Flags]
    public enum Needs { Nothing = 0, Part = 1, Assembly = 2, Drawing = 4, Model = Part | Assembly }

    public sealed class Tool
    {
        public Tool(string key, string title, string hint, bool active, Needs needs, string icon)
        { Key = key; Title = title; Hint = hint; Active = active; Needs = needs; Icon = icon; }
        public string Key { get; }      // GOKWORKS tool key ("" = main window only)
        public string Title { get; }
        public string Hint { get; }
        public bool Active { get; }     // pass --active: the tool reads the active SolidWorks model
        public Needs Needs { get; }
        public string Icon { get; }     // icon strip column (see make_icons.py)
    }

    public static class Tools
    {
        // Order = toolbar/menu order = icon strip order.
        public static readonly IReadOnlyList<Tool> All = new[]
        {
            new Tool("", "GOKWORKS", "GOKWORKS ana penceresini açar", false, Needs.Nothing, "app"),
            new Tool("automatic_drawing", "Otomatik Teknik Resim", "Açık parça veya montajın teknik resmini hazırlar", true, Needs.Model, "automatic_drawing"),
            new Tool("weight", "Ağırlık hesabı", "Açık modelin kütlesini ve ağırlığını hesaplar", true, Needs.Model, "weight"),
            new Tool("bom", "BOM · Ürün ağacı", "Açık montajın parça listesini okur", true, Needs.Assembly, "bom"),
            new Tool("naming", "İsimlendirme aracı", "Açık montajın bileşenlerini adlandırır", true, Needs.Assembly, "naming"),
            new Tool("dxf_dwg", "DXF / DWG", "Açık montajdaki sac parçaları DXF/DWG olarak tarar", true, Needs.Model, "dxf_dwg"),
            new Tool("press_brake", "Abkant Simülasyonu", "Açık sac parçayı abkant simülasyonuna alır", true, Needs.Part, "press_brake"),
            new Tool("tolerance_stack", "Tolerans yığılması", "Açık teknik resmin ölçülerini okur", true, Needs.Drawing, "tolerance_stack"),
            new Tool("dfm_analyzer", "DFM · İmalat uygunluğu", "DFM aracını açar", false, Needs.Nothing, "dfm_analyzer"),
            new Tool("sheet_unfolding", "Sac Açınımı", "Sac açınımı aracını açar", false, Needs.Nothing, "sheet_unfolding"),
            new Tool("nesting", "Nesting · Sac maliyeti", "Nesting aracını açar", false, Needs.Nothing, "nesting"),
        };

        /// <summary>Command line for GOKWORKS: <c>--open key [--active]</c>; empty for the main window.</summary>
        public static string Arguments(Tool tool)
        {
            if (tool.Key.Length == 0) return "";
            return "--open " + tool.Key + (tool.Active ? " --active" : "");
        }

        /// <summary>Does the active document satisfy the tool (SolidWorks type 1 part, 2 assembly, 3 drawing)?</summary>
        public static bool Accepts(Tool tool, int documentType)
        {
            if (tool.Needs == Needs.Nothing) return true;
            Needs kind = documentType == 1 ? Needs.Part : documentType == 2 ? Needs.Assembly
                       : documentType == 3 ? Needs.Drawing : Needs.Nothing;
            return kind != Needs.Nothing && (tool.Needs & kind) != 0;
        }

        /// <summary>
        /// GOKWORKS.exe: GOKWORKS_EXE, then HKCU\Software\GOKWORKS\SolidWorksAddin "Executable"
        /// (+ optional "Arguments", e.g. a python.exe + main.py development setup), then
        /// GOKWORKS.exe next to or one folder above this add-in.
        /// </summary>
        public static ProcessStartInfo StartInfo(Tool tool, string addinFolder)
        {
            string executable = Environment.GetEnvironmentVariable("GOKWORKS_EXE");
            string prefix = "";
            if (string.IsNullOrWhiteSpace(executable))
            {
                using (RegistryKey key = Registry.CurrentUser.OpenSubKey(@"Software\GOKWORKS\SolidWorksAddin"))
                {
                    executable = key?.GetValue("Executable") as string;
                    prefix = key?.GetValue("Arguments") as string ?? "";
                }
            }
            if (string.IsNullOrWhiteSpace(executable))
            {
                foreach (string folder in new[] { addinFolder, Path.GetDirectoryName(addinFolder) })
                {
                    if (folder == null) continue;
                    string candidate = Path.Combine(folder, "GOKWORKS.exe");
                    if (File.Exists(candidate)) { executable = candidate; break; }
                }
            }
            if (string.IsNullOrWhiteSpace(executable) || !File.Exists(executable))
                throw new FileNotFoundException(
                    "GOKWORKS.exe bulunamadı. Eklentiyi GOKWORKS klasörüne kurun veya " +
                    @"HKCU\Software\GOKWORKS\SolidWorksAddin\Executable değerini GOKWORKS.exe yoluna ayarlayın.");
            string arguments = (prefix + " " + Arguments(tool)).Trim();
            return new ProcessStartInfo(executable, arguments)
            {
                UseShellExecute = false,
                WorkingDirectory = Path.GetDirectoryName(executable),
            };
        }
    }
}
