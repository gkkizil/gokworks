// Test-only .NET Framework transparent proxies. No SOLIDWORKS activation/CAD.
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.Remoting.Messaging;
using System.Runtime.Remoting.Proxies;
using SolidWorks.Interop.sldworks;

namespace Gokworks.ShaftChannelTest
{
    public sealed class KeywayDepthProbe
    {
        public bool Accepted;
        public string Parameter;
        public string Renamed;
        public string Error;
        public double Measured;

        public static KeywayDepthProbe Bind(MethodInfo method, string mode)
        {
            KeywayDepthProbe probe=new KeywayDepthProbe();
            object dimension=Proxy.Make(typeof(IDimension),delegate(IMethodCallMessage call) {
                if(call.MethodName=="get_DrivenState") return mode=="reference" ? 1 : 2;
                if(call.MethodName=="get_SystemValue") return mode=="wrong_dimension" ? .003 : .004;
                if(call.MethodName=="set_Name") { probe.Renamed=(string)call.Args[0]; return null; }
                if(call.MethodName=="get_Name") return probe.Renamed;
                throw new InvalidOperationException("Unexpected depth dimension call: "+call.MethodName);
            });
            object data=Proxy.Make(typeof(IExtrudeFeatureData2),delegate(IMethodCallMessage call) {
                if(!(bool)call.Args[0]) throw new InvalidOperationException("Forward depth required.");
                if(call.MethodName=="GetEndCondition") return mode=="not_blind" ? 1 : 0;
                if(call.MethodName=="GetDepth") return mode=="wrong_travel" ? .005 : .004;
                throw new InvalidOperationException("Unexpected cut definition call: "+call.MethodName);
            });
            object feature=Proxy.Make(typeof(IFeature),delegate(IMethodCallMessage call) {
                if(call.MethodName=="GetDefinition") return data;
                if(call.MethodName=="Parameter")
                { probe.Parameter=(string)call.Args[0]; return mode=="missing" ? null : dimension; }
                // Fail if the shipping code assumes only one display dimension.
                throw new InvalidOperationException("Unexpected cut feature call: "+call.MethodName);
            });
            try { method.Invoke(null,new object[]{feature,.004}); probe.Accepted=true; }
            catch(TargetInvocationException error)
            {
                if(!(error.InnerException is InvalidOperationException)) throw;
                probe.Error=error.InnerException.Message;
            }
            return probe;
        }

        private static object Face(bool planar,double[] parameters)
        {
            object surface=Proxy.Make(typeof(ISurface),delegate(IMethodCallMessage call) {
                if(call.MethodName=="IsPlane") return planar;
                if(call.MethodName=="get_PlaneParams") return parameters;
                throw new InvalidOperationException(call.MethodName);
            });
            return Proxy.Make(typeof(IFace2),delegate(IMethodCallMessage call) {
                if(call.MethodName=="GetSurface") return surface;
                throw new InvalidOperationException(call.MethodName);
            });
        }

        public static KeywayDepthProbe Inspect(MethodInfo method,double actualDepth,bool rotated,string mode)
        {
            KeywayDepthProbe probe=new KeywayDepthProbe();
            double[] origin={.1,.2,.3}, radial=rotated ? new double[]{0,0,-1} : new double[]{0,1,0};
            double height=(22.5-actualDepth)*.001;
            // Plane normal may oppose the shaft radial axis; plane root may be
            // translated along the floor. Neither changes measured radial depth.
            double[] parameters={-radial[0],-radial[1],-radial[2],
                origin[0]+.017,origin[1]+height*radial[1],origin[2]+height*radial[2]};
            var faces=new List<object>();
            faces.Add(Face(false,null));
            faces.Add(Face(true,new double[]{1,0,0,.12,.22,.33})); // axial end, not pocket floor
            if(mode!="missing") faces.Add(Face(true,parameters));
            if(mode=="split") faces.Add(Face(true,parameters));
            if(mode=="ambiguous")
            {
                double[] other=(double[])parameters.Clone();
                for(int i=0;i<3;i++) other[i+3]+=.001*radial[i];
                faces.Add(Face(true,other));
            }
            object feature=Proxy.Make(typeof(IFeature),delegate(IMethodCallMessage call) {
                if(call.MethodName=="GetFaces") return faces.ToArray();
                throw new InvalidOperationException(call.MethodName);
            });
            try { probe.Measured=(double)method.Invoke(null,new object[]{feature,45.0,3.0,origin,radial}); probe.Accepted=true; }
            catch(TargetInvocationException error)
            {
                if(!(error.InnerException is InvalidOperationException)) throw;
                probe.Error=error.InnerException.Message;
            }
            return probe;
        }
    }

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
            try
            {
                object value=respond(call);
                Reply reply=value as Reply;
                return reply==null ? new ReturnMessage(value,null,0,call.LogicalCallContext,call)
                    : new ReturnMessage(reply.Value,reply.Arguments,reply.Arguments.Length,call.LogicalCallContext,call);
            }
            catch (Exception error) { return new ReturnMessage(error, call); }
        }
        internal static object Make(Type contract, Func<IMethodCallMessage, object> handler)
        { return new Proxy(contract, handler).GetTransparentProxy(); }
    }

    internal sealed class Reply
    {
        internal readonly object Value;
        internal readonly object[] Arguments;
        internal Reply(object value,object[] arguments) { Value=value; Arguments=arguments; }
    }

    public sealed class Probe
    {
        public readonly List<string> Events = new List<string>();
        public readonly IModelDoc2 Model;
        public readonly IFeature Sketch;
        public readonly ISketchSegment Axis;
        public bool RefuseAxis;
        public bool RefuseSketch;
        public bool ExtraSelection;
        public int ProfileStatus;
        public int OpenContours;
        public int ClosedContours=1;
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
            object drawing=Proxy.Make(typeof(ISketch),delegate(IMethodCallMessage call) {
                if(call.MethodName!="CheckFeatureUse") throw new InvalidOperationException(call.MethodName);
                Events.Add("profile:"+call.Args[0]);
                object[] arguments=(object[])call.Args.Clone();
                arguments[1]=OpenContours; arguments[2]=ClosedContours;
                return new Reply(ProfileStatus,arguments);
            });
            Sketch = (IFeature)Proxy.Make(typeof(IFeature), delegate(IMethodCallMessage call) {
                if(call.MethodName=="GetSpecificFeature2") return drawing;
                if (call.MethodName != "Select2") throw new InvalidOperationException(call.MethodName);
                Events.Add("sketch:" + call.Args[0] + ":" + call.Args[1]);
                if(RefuseSketch) return false;
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

        public bool SelectKeyway(MethodInfo method)
        {
            try { method.Invoke(null,new object[]{Model,Sketch}); return true; }
            catch(TargetInvocationException error)
            {
                if(!(error.InnerException is InvalidOperationException)) throw;
                Events.Add("rejected:"+error.InnerException.Message); return false;
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
