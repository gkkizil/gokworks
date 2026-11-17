// SolidWorks add-in: a GOKWORKS menu, toolbar and CommandManager tab.
// GOKWORKS itself runs as its own process (Python/Qt never loads inside SolidWorks):
// a command starts GOKWORKS.exe --open <tool> [--active]; a running GOKWORKS window
// receives the command instead (gui_qt/remote.py), and the tool reads the active model
// through GOKWORKS' existing SolidWorks connection.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swpublished;

namespace Gokworks.SolidWorksAddin
{
    [ComVisible(true)]
    [Guid("6F1C0A52-9B0E-4C7B-A3D4-2E8B5C9F0D17")]
    [ProgId("Gokworks.SolidWorksAddin")]
    public class GokworksAddin : ISwAddin
    {
        const int GroupId = 4710;                    // CommandManager user id of the GOKWORKS group
        const string Title = "GOKWORKS";
        const int MenuItem = 1, ToolbarItem = 2;     // swCommandItemType_e
        const int TextBelow = 2;                     // swCommandTabButtonTextDisplay_e.swCommandTabButton_TextBelow
        static readonly int[] DocumentTypes = { 1, 2, 3 };   // swDocPART, swDocASSEMBLY, swDocDRAWING
        static readonly int[] IconSizes = { 20, 32, 40, 64, 96, 128 };

        ISldWorks app;
        ICommandManager commands;
        int cookie;
        readonly Dictionary<int, Tool> commandTools = new Dictionary<int, Tool>();

        static string Folder => Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);

        public bool ConnectToSW(object ThisSW, int Cookie)
        {
            app = (ISldWorks)ThisSW;
            cookie = Cookie;
            app.SetAddinCallbackInfo2(0, this, cookie);
            commands = app.GetCommandManager(cookie);
            CreateCommands();
            return true;
        }

        public bool DisconnectFromSW()
        {
            try { commands?.RemoveCommandGroup2(GroupId, true); }
            finally
            {
                if (commands != null) Marshal.ReleaseComObject(commands);
                commands = null;
                if (app != null) Marshal.ReleaseComObject(app);
                app = null;
                GC.Collect(); GC.WaitForPendingFinalizers();
            }
            return true;
        }

        void CreateCommands()
        {
            int errors = 0;
            // Rebuild the group when the saved toolbar layout no longer matches these commands.
            bool ignorePrevious = false;
            if (commands.GetGroupDataFromRegistry(GroupId, out object saved))
                ignorePrevious = !(saved is int[] ids) || ids.Length != Tools.All.Count;
            CommandGroup group = commands.CreateCommandGroup2(GroupId, Title, "GOKWORKS mühendislik araçları",
                                                              "GOKWORKS mühendislik araçları", -1, ignorePrevious, ref errors);
            group.IconList = IconSizes.Select(size => Path.Combine(Folder, "icons", $"tools_{size}.png")).ToArray();
            group.MainIconList = IconSizes.Select(size => Path.Combine(Folder, "icons", $"main_{size}.png")).ToArray();
            var indices = new List<int>();
            for (int i = 0; i < Tools.All.Count; i++)
            {
                Tool tool = Tools.All[i];
                indices.Add(group.AddCommandItem2(tool.Title, -1, tool.Hint, tool.Title, i,
                                                  $"Run{i}", $"Enable{i}", i, MenuItem | ToolbarItem));
            }
            group.HasToolbar = true;
            group.HasMenu = true;
            group.Activate();
            for (int i = 0; i < indices.Count; i++)
                commandTools[group.get_CommandID(indices[i])] = Tools.All[i];

            foreach (int type in DocumentTypes)
            {
                CommandTab tab = commands.GetCommandTab(type, Title);
                if (tab != null && ignorePrevious) { commands.RemoveCommandTab(tab); tab = null; }
                if (tab != null) continue;
                tab = commands.AddCommandTab(type, Title);
                CommandTabBox box = tab.AddCommandTabBox();
                int[] ids = indices.Select(index => group.get_CommandID(index)).ToArray();
                int[] text = ids.Select(_ => TextBelow).ToArray();
                box.AddCommands(ids, text);
            }
        }

        // --- CommandManager callbacks (looked up by name: Run0..Run10, Enable0..Enable10) ----------------
        void Run(int index)
        {
            Tool tool = Tools.All[index];
            try
            {
                Process.Start(Tools.StartInfo(tool, Folder))?.Dispose();
            }
            catch (Exception error)
            {
                MessageBox.Show(error.Message, "GOKWORKS", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        int Enable(int index)
        {
            Tool tool = Tools.All[index];
            if (tool.Needs == Needs.Nothing) return 1;
            object document = app?.ActiveDoc;
            if (!(document is IModelDoc2 model)) return 0;
            try { return Tools.Accepts(tool, model.GetType()) ? 1 : 0; }
            finally { Marshal.ReleaseComObject(document); }
        }

        public void Run0() => Run(0);   public int Enable0() => Enable(0);
        public void Run1() => Run(1);   public int Enable1() => Enable(1);
        public void Run2() => Run(2);   public int Enable2() => Enable(2);
        public void Run3() => Run(3);   public int Enable3() => Enable(3);
        public void Run4() => Run(4);   public int Enable4() => Enable(4);
        public void Run5() => Run(5);   public int Enable5() => Enable(5);
        public void Run6() => Run(6);   public int Enable6() => Enable(6);
        public void Run7() => Run(7);   public int Enable7() => Enable(7);
        public void Run8() => Run(8);   public int Enable8() => Enable(8);
        public void Run9() => Run(9);   public int Enable9() => Enable(9);
        public void Run10() => Run(10); public int Enable10() => Enable(10);

        // --- COM registration (RegAsm /codebase) -------------------------------------------------------
        [ComRegisterFunction]
        public static void Register(Type type)
        {
            string id = "{" + type.GUID.ToString().ToUpperInvariant() + "}";
            using (RegistryKey key = Registry.LocalMachine.CreateSubKey(@"SOFTWARE\SolidWorks\Addins\" + id))
            {
                key.SetValue(null, 0);
                key.SetValue("Description", "GOKWORKS mühendislik araçlarını SolidWorks menüsünden açar.");
                key.SetValue("Title", Title);
            }
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(@"Software\SolidWorks\AddInsStartup\" + id))
                key.SetValue(null, 1, RegistryValueKind.DWord);
        }

        [ComUnregisterFunction]
        public static void Unregister(Type type)
        {
            string id = "{" + type.GUID.ToString().ToUpperInvariant() + "}";
            Registry.LocalMachine.DeleteSubKey(@"SOFTWARE\SolidWorks\Addins\" + id, false);
            Registry.CurrentUser.DeleteSubKey(@"Software\SolidWorks\AddInsStartup\" + id, false);
        }
    }
}
