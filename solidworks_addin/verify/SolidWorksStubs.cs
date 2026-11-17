// COMPILE CHECK ONLY (dotnet build -p:SwStubs=true). Never shipped.
// Signatures of exactly the SolidWorks API members the add-in uses, as published in the
// SolidWorks API help (ISwAddin, ISldWorks, ICommandManager, ICommandGroup, ICommandTab,
// ICommandTabBox, IModelDoc2). A real build references the SolidWorks interop assemblies.
namespace SolidWorks.Interop.swpublished
{
    public interface ISwAddin
    {
        bool ConnectToSW(object ThisSW, int Cookie);
        bool DisconnectFromSW();
    }
}

namespace SolidWorks.Interop.sldworks
{
    public interface ISldWorks
    {
        bool SetAddinCallbackInfo2(int ModuleHandle, object AddinCallbacks, int Cookie);
        CommandManager GetCommandManager(int Cookie);
        object ActiveDoc { get; }
    }

    public interface ICommandManager
    {
        CommandGroup CreateCommandGroup2(int UserID, string Title, string ToolTip, string Hint, int Position,
                                         bool IgnorePreviousVersion, ref int Errors);
        bool RemoveCommandGroup2(int UserID, bool RunInBackground);
        bool GetGroupDataFromRegistry(int UserID, out object IDList);
        CommandTab GetCommandTab(int Type, string Name);
        CommandTab AddCommandTab(int Type, string Name);
        bool RemoveCommandTab(CommandTab Tab);
    }
    public interface CommandManager : ICommandManager { }

    public interface ICommandGroup
    {
        object IconList { get; set; }
        object MainIconList { get; set; }
        bool HasToolbar { get; set; }
        bool HasMenu { get; set; }
        int AddCommandItem2(string Name, int Position, string HintString, string ToolTip, int ImageListIndex,
                            string CallbackFunction, string EnableMethod, int UserID, int MenuTBOption);
        bool Activate();
        int get_CommandID(int Index);
    }
    public interface CommandGroup : ICommandGroup { }

    public interface ICommandTab { CommandTabBox AddCommandTabBox(); }
    public interface CommandTab : ICommandTab { }
    public interface ICommandTabBox { bool AddCommands(object CommandIDs, object TextType); }
    public interface CommandTabBox : ICommandTabBox { }

    public interface IModelDoc2 { int GetType(); }
}
