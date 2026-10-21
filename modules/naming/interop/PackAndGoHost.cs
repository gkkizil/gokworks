// GOKWORKS internal Pack and Go transport. Compiled against the user's own
// installed SolidWorks interop assembly; no SolidWorks DLL is redistributed.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

namespace Gokworks.PackAndGoInterop
{
    public static class Host
    {
        [DllImport("oleaut32.dll", PreserveSig = false)]
        private static extern void GetActiveObject(ref Guid clsid, IntPtr reserved,
            [MarshalAs(UnmanagedType.IUnknown)] out object value);

        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer
            { MaxJsonLength = 33554432, RecursionLimit = 32 };

        private static string Text(Dictionary<string, object> request, string key)
        {
            object value;
            if (!request.TryGetValue(key, out value) || !(value is string))
                throw new ArgumentException("Missing string: " + key);
            return (string)value;
        }

        private static bool Flag(Dictionary<string, object> request, string key)
        {
            object value;
            if (!request.TryGetValue(key, out value) || !(value is bool))
                throw new ArgumentException("Missing boolean: " + key);
            return (bool)value;
        }

        private static bool SamePath(string left, string right)
        {
            return String.Equals(Path.GetFullPath(left), Path.GetFullPath(right), StringComparison.OrdinalIgnoreCase);
        }

        private static void Release(object value)
        {
            if (value != null && Marshal.IsComObject(value)) Marshal.ReleaseComObject(value);
        }

        private static object Execute(IPackAndGo pack, IModelDocExtension extension,
            IModelDoc2 model, Dictionary<string, object> request)
        {
            string operation = Text(request, "operation");
            object names, states;
            switch (operation)
            {
                case "get_names":
                    if (!pack.GetDocumentNames(out names)) throw new InvalidOperationException("GetDocumentNames returned false.");
                    return names;
                case "get_targets":
                    if (!pack.GetDocumentSaveToNames(out names, out states)) throw new InvalidOperationException("GetDocumentSaveToNames returned false.");
                    return new object[] { names, states };
                case "count": return pack.GetDocumentNamesCount();
                case "set_folder": return pack.SetSaveToName(Flag(request, "override"), Text(request, "path"));
                case "set_targets":
                    object raw;
                    if (!request.TryGetValue("paths", out raw) || !(raw is IEnumerable) || raw is string)
                        throw new ArgumentException("Missing paths array.");
                    var paths = new List<string>();
                    foreach (object item in (IEnumerable)raw)
                    {
                        if (!(item is string)) throw new ArgumentException("Invalid target path.");
                        paths.Add((string)item);
                    }
                    return pack.SetDocumentSaveToNames(paths.ToArray());
                case "get_flag":
                    switch (Text(request, "name"))
                    {
                        case "IncludeDrawings": return pack.IncludeDrawings;
                        case "IncludeSuppressed": return pack.IncludeSuppressed;
                        case "IncludeToolboxComponents": return pack.IncludeToolboxComponents;
                        case "IncludeSimulationResults": return pack.IncludeSimulationResults;
                        case "FlattenToSingleFolder": return pack.FlattenToSingleFolder;
                        default: throw new ArgumentException("Unsupported Pack and Go flag.");
                    }
                case "set_flag":
                    bool value = Flag(request, "value");
                    switch (Text(request, "name"))
                    {
                        case "IncludeDrawings": pack.IncludeDrawings = value; break;
                        case "IncludeSuppressed": pack.IncludeSuppressed = value; break;
                        case "IncludeToolboxComponents": pack.IncludeToolboxComponents = value; break;
                        case "IncludeSimulationResults": pack.IncludeSimulationResults = value; break;
                        case "FlattenToSingleFolder": pack.FlattenToSingleFolder = value; break;
                        default: throw new ArgumentException("Unsupported Pack and Go flag.");
                    }
                    return true;
                case "set_text":
                    switch (Text(request, "name"))
                    {
                        case "AddPrefix": pack.AddPrefix = Text(request, "value"); break;
                        case "AddSuffix": pack.AddSuffix = Text(request, "value"); break;
                        default: throw new ArgumentException("Unsupported Pack and Go text.");
                    }
                    return true;
                case "save":
                    if (model.GetSaveFlag()) throw new InvalidOperationException("Source has unsaved changes; package was not saved.");
                    return extension.SavePackAndGo((PackAndGo)pack);
                default: throw new ArgumentException("Unsupported operation.");
            }
        }

        [STAThread]
        public static void Run()
        {
            // PowerShell hosts the call on STA; no windows or independent UI.
            ISldWorks app = null;
            IModelDoc2 model = null;
            IModelDocExtension extension = null;
            IPackAndGo pack = null;
            object application = null;
            try
            {
                var init = Json.Deserialize<Dictionary<string, object>>(Console.ReadLine());
                Type server = Type.GetTypeFromProgID("SldWorks.Application", true);
                Guid clsid = server.GUID;
                GetActiveObject(ref clsid, IntPtr.Zero, out application);
                app = (ISldWorks)application;
                int process = Convert.ToInt32(init["process_id"]);
                if (process <= 0 || app.GetProcessID() != process)
                    throw new InvalidOperationException("SolidWorks session changed; read the source again.");
                string root = Text(init, "source");
                model = (IModelDoc2)app.GetOpenDocumentByName(root);
                if (model == null || !SamePath(model.GetPathName(), root))
                    throw new InvalidOperationException("Selected source is no longer open.");
                if (model.GetSaveFlag()) throw new InvalidOperationException("Source has unsaved changes.");
                extension = (IModelDocExtension)model.Extension;
                // Strongly typed dual-interface call. Do not use C# dynamic or
                // reflection dispatch: those would repeat IDispatch::Invoke.
                pack = (IPackAndGo)extension.GetPackAndGo();
                if (pack == null) throw new InvalidOperationException("GetPackAndGo returned null.");
                Console.WriteLine(Json.Serialize(new { ok = true, backend = "SolidWorks .NET interop", process_id = process }));
                Console.Out.Flush();
                string line;
                while ((line = Console.ReadLine()) != null)
                {
                    try
                    {
                        var request = Json.Deserialize<Dictionary<string, object>>(line);
                        if (Text(request, "operation") == "close") break;
                        object result = Execute(pack, extension, model, request);
                        Console.WriteLine(Json.Serialize(new { ok = true, result = result }));
                    }
                    catch (Exception error)
                    {
                        Console.WriteLine(Json.Serialize(new { ok = false, error = error.Message, hresult = error.HResult }));
                    }
                    Console.Out.Flush();
                }
            }
            catch (Exception error)
            {
                Console.WriteLine(Json.Serialize(new { ok = false, error = error.Message, hresult = error.HResult }));
                Console.Out.Flush();
            }
            finally
            {
                Release(pack); Release(extension); Release(model); Release(application);
                // Never close/quit/save a user's document or SolidWorks here.
            }
        }
    }
}
