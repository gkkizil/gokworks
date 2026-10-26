// Test-only .NET Framework transparent proxies. No SOLIDWORKS activation/CAD.
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.Remoting.Messaging;
using System.Runtime.Remoting.Proxies;
using SolidWorks.Interop.sldworks;

namespace Gokworks.ShaftChannelTest
{
    public sealed class FilletProbe
    {
        public readonly Dictionary<string, object> Values = new Dictionary<string, object>();
        public bool CreateCalled;
        public bool CorrectDefinition;
        public int EdgeCount;
        public bool Rejected;
        public static FilletProbe Capture(MethodInfo method, bool refuseInitialize)
        {
            FilletProbe probe=new FilletProbe();
            object definition=Proxy.Make(typeof(ISimpleFilletFeatureData2), delegate(IMethodCallMessage call) {
                if(call.MethodName=="Initialize")
                { probe.Values["Initialize"]=(int)call.Args[0]; return !refuseInitialize; }
                if(call.MethodName.StartsWith("set_"))
                {
                    string key=call.MethodName.Substring(4);
                    if(key=="Edges") probe.EdgeCount=((object[])call.Args[0]).Length;
                    else probe.Values[key]=call.Args[0];
                    return null;
                }
                throw new InvalidOperationException("Unexpected fillet data call: "+call.MethodName);
            });
            object manager=Proxy.Make(typeof(IFeatureManager), delegate(IMethodCallMessage call) {
                if(call.MethodName=="CreateDefinition")
                { probe.Values["Definition"]=(int)call.Args[0]; return definition; }
                if(call.MethodName=="CreateFeature")
                {
                    probe.CreateCalled=true;
                    probe.CorrectDefinition=Object.ReferenceEquals(call.Args[0],definition);
                    return null; // No geometry kernel, no fabricated successful feature.
                }
                throw new InvalidOperationException("Unexpected fillet manager call: "+call.MethodName);
            });
            object edge=Proxy.Make(typeof(IEdge), delegate(IMethodCallMessage call) {
                throw new InvalidOperationException("Unexpected edge call: "+call.MethodName);
            });
            try { method.Invoke(null,new object[]{manager,edge,.001}); }
            catch(TargetInvocationException error)
            {
                if(!(error.InnerException is InvalidOperationException)) throw;
                probe.Rejected=true;
            }
            return probe;
        }
    }

    internal sealed class Proxy : RealProxy
    {
        private readonly Func<IMethodCallMessage, object> respond;
        internal Proxy(Type contract, Func<IMethodCallMessage, object> handler) : base(contract)
        { respond = handler; }
        public override IMessage Invoke(IMessage message)
        {
            IMethodCallMessage call = (IMethodCallMessage)message;
            try { return new ReturnMessage(respond(call), null, 0, call.LogicalCallContext, call); }
            catch (Exception error) { return new ReturnMessage(error, call); }
        }
        internal static object Make(Type contract, Func<IMethodCallMessage, object> handler)
        { return new Proxy(contract, handler).GetTransparentProxy(); }
    }

    public sealed class Probe
    {
        public readonly List<string> Events = new List<string>();
        public readonly IModelDoc2 Model;
        public readonly IFeature Sketch;
        public readonly ISketchSegment Axis;
        public bool RefuseAxis;
        public bool ExtraSelection;
        private readonly List<int> marks = new List<int>();
        private int axisMark;

        public Probe()
        {
            object data = Proxy.Make(typeof(SelectData), delegate(IMethodCallMessage call) {
                if (call.MethodName == "set_Mark") { axisMark = (int)call.Args[0]; return null; }
                if (call.MethodName == "get_Mark") return axisMark;
                throw new InvalidOperationException("Unexpected select-data call: " + call.MethodName);
            });
            object selection = Proxy.Make(typeof(ISelectionMgr), delegate(IMethodCallMessage call) {
                if (call.MethodName == "set_EnableContourSelection")
                { Events.Add("contours:" + call.Args[0]); return null; }
                if (call.MethodName == "CreateSelectData") return data;
                if (call.MethodName == "GetSelectedObjectCount2")
                {
                    int mark = (int)call.Args[0];
                    if (mark == -1) return marks.Count + (ExtraSelection ? 1 : 0);
                    return marks.FindAll(delegate(int value) { return value == mark; }).Count;
                }
                throw new InvalidOperationException("Unexpected selection call: " + call.MethodName);
            });
            object manager = Proxy.Make(typeof(SketchManager), delegate(IMethodCallMessage call) {
                if (call.MethodName == "set_AddToDB")
                { Events.Add("add-to-db:" + call.Args[0]); return null; }
                throw new InvalidOperationException("Unexpected sketch-manager call: " + call.MethodName);
            });
            Model = (IModelDoc2)Proxy.Make(typeof(IModelDoc2), delegate(IMethodCallMessage call) {
                if (call.MethodName == "get_SelectionManager") return selection;
                if (call.MethodName == "get_SketchManager") return manager;
                if (call.MethodName == "ClearSelection2")
                { Events.Add("clear:" + call.Args[0]); marks.Clear(); return null; }
                if (call.MethodName == "GetTitle") return "Mil_inceleme";
                // A save/close/rebuild would fail the probe instead of silently succeeding.
                throw new InvalidOperationException("Unexpected document call: " + call.MethodName);
            });
            Sketch = (IFeature)Proxy.Make(typeof(IFeature), delegate(IMethodCallMessage call) {
                if (call.MethodName != "Select2") throw new InvalidOperationException(call.MethodName);
                Events.Add("sketch:" + call.Args[0] + ":" + call.Args[1]);
                if (!(bool)call.Args[0]) marks.Clear();
                marks.Add((int)call.Args[1]); return true;
            });
            Axis = (ISketchSegment)Proxy.Make(typeof(ISketchSegment), delegate(IMethodCallMessage call) {
                if (call.MethodName == "get_ConstructionGeometry") return true;
                if (call.MethodName != "Select4") throw new InvalidOperationException(call.MethodName);
                Events.Add("axis:" + call.Args[0] + ":" + axisMark);
                if (RefuseAxis) return false;
                if (!(bool)call.Args[0]) marks.Clear();
                marks.Add(axisMark); return true;
            });
        }

        public bool Select(MethodInfo method)
        {
            try { method.Invoke(null, new object[] { Model, Sketch, Axis }); return true; }
            catch (TargetInvocationException error)
            {
                if (!(error.InnerException is InvalidOperationException)) throw;
                Events.Add("rejected:" + error.InnerException.Message); return false;
            }
        }

        // Keep COM proxies inside C#. PowerShell's adapter calls GetType while
        // marshalling a proxy property, colliding with IModelDoc2.GetType().
        public string Preserve(MethodInfo method)
        { return (string)method.Invoke(null, new object[] { Model }); }

        public string PreserveEmpty(MethodInfo method)
        { return (string)method.Invoke(null, new object[] { null }); }
    }
}
