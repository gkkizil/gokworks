// Native SOLIDWORKS features only. Compiled on Windows against the running
// installation's interop assemblies; these DLLs are never bundled by GOKWORKS.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace Gokworks.ShaftInterop
{
    public class Stage { public string id; public double diameter; public double length; }
    public class Operation
    {
        public string id; public string kind; public string stage_id; public string edge;
        public double offset; public double width; public double depth; public double length;
        public double angle; public double distance; public double radius;
    }
    public class Project
    {
        public string schema; public int version; public string units; public string name;
        public Stage[] stages; public Operation[] operations; public double minimum_wall;
    }
    public class Request
    {
        public string operation; public int process_id; public Project project;
        public string output_path; public bool verify_edit;
    }

    public static class Host
    {
        [DllImport("oleaut32.dll", PreserveSig = false)]
        private static extern void GetActiveObject(ref Guid clsid, IntPtr reserved,
            [MarshalAs(UnmanagedType.IUnknown)] out object value);

        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer
            { MaxJsonLength = 2000000, RecursionLimit = 32 };
        public static object ConnectRunningApplication(string progId)
        {
            // SldWorks is an interop interface with a CoClass attribute. Its
            // GUID is an IID, not the registered application's CLSID.
            Type server = Type.GetTypeFromProgID(progId, true);
            Guid clsid = server.GUID;
            object active;
            GetActiveObject(ref clsid, IntPtr.Zero, out active);
            return active;
        }
        internal static void Need(bool condition, string message)
        {
            if (!condition) throw new InvalidOperationException(message);
        }
        internal static string PreserveFailedPart(IModelDoc2 model)
        {
            // This is our NEW document. Keep its last successful features and
            // failing sketch available for inspection; never save or close it.
            if (model == null) return "";
            model.SketchManager.AddToDB = false;
            return model.GetTitle();
        }
        private static string lastPhase = "Başlangıç";
        internal static void Report(string phase)
        {
            lastPhase = phase;
            Console.WriteLine(Json.Serialize(new { @event = "shaft_phase", phase = phase }));
        }
        private static bool Positive(double value)
        { return !Double.IsNaN(value) && !Double.IsInfinity(value) && value >= .00001 && value <= 1000000; }

        private static void Validate(Request request)
        {
            Need(request != null && request.operation == "create_shaft" && request.process_id > 0, "Invalid shaft request.");
            Project p = request.project;
            Need(p != null && p.schema == "gokworks.shaft" && p.version == 1 && p.units == "mm", "Unsupported shaft schema.");
            Need(!String.IsNullOrWhiteSpace(p.name) && p.name.Length <= 80 && p.name.IndexOfAny(Path.GetInvalidFileNameChars()) < 0, "Invalid part name.");
            Need(p.stages != null && p.stages.Length >= 1 && p.stages.Length <= 100 && p.operations != null && p.operations.Length <= 200, "Invalid stage/operation count.");
            Need(Positive(p.minimum_wall), "Invalid minimum wall.");
            var stages = new Dictionary<string, Stage>(); double total = 0;
            foreach (Stage s in p.stages)
            {
                Need(s != null && !String.IsNullOrEmpty(s.id) && !stages.ContainsKey(s.id) && Positive(s.diameter) && Positive(s.length), "Invalid stage.");
                stages.Add(s.id, s); total += s.length;
            }
            Need(Positive(total), "Invalid total length.");
            foreach (Operation op in p.operations)
            {
                Need(op != null && stages.ContainsKey(op.stage_id), "Missing operation stage.");
                Stage s = stages[op.stage_id];
                if (op.kind == "groove" || op.kind == "keyway")
                {
                    double extent = op.kind == "groove" ? op.width : op.length;
                    Need(op.offset >= 0 && !Double.IsNaN(op.offset) && Positive(extent) && Positive(op.depth)
                        && op.offset + extent <= s.length + 1e-8 && s.diameter / 2 - op.depth >= p.minimum_wall, "Invalid channel geometry.");
                    if (op.kind == "keyway")
                        Need(op.angle == 0 && Positive(op.width) && op.length-op.width >= .00001 && op.width < s.diameter
                            && Math.Pow(op.width/2,2)+Math.Pow(s.diameter/2-op.depth,2) < Math.Pow(s.diameter/2,2), "Unsupported keyway.");
                }
                else if (op.kind == "chamfer") Need(op.angle == 45 && Positive(op.distance), "Only 45 degree chamfers are supported.");
                else if (op.kind == "fillet") Need(Positive(op.radius), "Invalid fillet radius.");
                else throw new InvalidOperationException("Unsupported shaft operation.");
                if (op.kind == "chamfer" || op.kind == "fillet") Need(op.edge == "left" || op.edge == "right", "Invalid edge.");
            }
            if (!String.IsNullOrEmpty(request.output_path))
            {
                string path = request.output_path;
                Need(Path.IsPathRooted(path) && String.Equals(Path.GetExtension(path), ".SLDPRT", StringComparison.OrdinalIgnoreCase)
                    && Directory.Exists(Path.GetDirectoryName(path)) && !File.Exists(path) && !Directory.Exists(path), "Output must be a NEW .SLDPRT path.");
            }
        }

        public static void Run()
        {
            ISldWorks app = null; IModelDoc2 model = null; string previous = null; string temporary = null;
            bool inputPreference = false; bool preferenceCaptured = false;
            try
            {
                Need(Thread.CurrentThread.GetApartmentState() == ApartmentState.STA, "Shaft host must run in STA.");
                string line = Console.ReadLine();
                if (line == null) return;
                Request request = Json.Deserialize<Request>(line); Validate(request);
                Report("Açık SOLIDWORKS oturumu doğrulanıyor");
                app = (ISldWorks)ConnectRunningApplication("SldWorks.Application");
                Need(app.GetProcessID() == request.process_id, "SOLIDWORKS session changed; no document was created.");
                IModelDoc2 old = (IModelDoc2)app.ActiveDoc;
                if (old != null) previous = old.GetTitle();
                Report("Yeni parça şablonu doğrulanıyor");
                string template = app.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart);
                Need(!String.IsNullOrWhiteSpace(template) && File.Exists(template),
                    "SOLIDWORKS varsayılan parça şablonu bulunamadı. Araçlar > Seçenekler > Varsayılan Şablonlar bölümünde geçerli bir .prtdot dosyası seçin.");
                inputPreference = app.GetUserPreferenceToggle((int)swUserPreferenceToggle_e.swInputDimValOnCreate);
                preferenceCaptured = true;
                app.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swInputDimValOnCreate, false);
                Need(!app.GetUserPreferenceToggle((int)swUserPreferenceToggle_e.swInputDimValOnCreate), "Dimension input preference could not be disabled.");
                Report("Yeni SOLIDWORKS parçası oluşturuluyor");
                model = (IModelDoc2)app.NewDocument(template, 0, 0, 0);
                Need(model != null && model.GetType() == (int)swDocumentTypes_e.swDocPART && String.IsNullOrEmpty(model.GetPathName()), "A new unsaved Part could not be created.");
                model.SetTitle2(request.project.name + "_" + Guid.NewGuid().ToString("N").Substring(0,8));
                model.ShowFeatureErrorDialog = false;
                var builder = new Builder(model, request.project, (IMathUtility)app.GetMathUtility());
                builder.Build();
                if (request.verify_edit) builder.VerifyEditable();
                bool zeroOffsetVerified = builder.ZeroOffsetVerified;
                builder.Verify();
                double volume = builder.Volume();
                if (!String.IsNullOrEmpty(request.output_path))
                {
                    Report("SLDPRT kaydediliyor ve yeniden açılıyor");
                    temporary = Path.Combine(Path.GetDirectoryName(request.output_path), ".gokworks-" + Guid.NewGuid().ToString("N") + ".SLDPRT");
                    int errors = 0; int warnings = 0;
                    Need(model.Extension.SaveAs(temporary, 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings)
                        && errors == 0 && File.Exists(temporary) && new FileInfo(temporary).Length > 0, "SLDPRT save failed: " + errors);
                    string ownTitle = model.GetTitle(); model = null;
                    app.CloseDoc(ownTitle); // only the document created above
                    File.Move(temporary, request.output_path); // atomic, refuses any overwrite
                    temporary = null;
                    model = (IModelDoc2)app.OpenDoc6(request.output_path, (int)swDocumentTypes_e.swDocPART,
                        (int)swOpenDocOptions_e.swOpenDocOptions_Silent, "", ref errors, ref warnings);
                    Need(model != null && errors == 0, "Saved part could not be reopened: " + request.output_path);
                    builder = new Builder(model, request.project, (IMathUtility)app.GetMathUtility());
                    builder.Verify();
                    Need(Math.Abs(builder.Volume()-volume) < Math.Max(1e-15,volume*1e-8), "Reopened part volume differs.");
                }
                model.ShowNamedView2("", (int)swStandardViews_e.swIsometricView); model.ViewZoomtofit2();
                app.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swInputDimValOnCreate, inputPreference);
                Need(app.GetUserPreferenceToggle((int)swUserPreferenceToggle_e.swInputDimValOnCreate)==inputPreference,
                    "Original dimension input preference could not be restored.");
                preferenceCaptured = false;
                Console.WriteLine(Json.Serialize(new {
                    success = true, process_id = request.process_id, document = model.GetTitle(),
                    output_path = request.output_path, feature_count = builder.ExpectedNames.Count,
                    features = builder.ExpectedNames.ToArray(), fully_defined = true, single_body = true,
                    rebuild_success = true, volume_m3 = volume, edit_verified = request.verify_edit,
                    zero_offset_verified = zeroOffsetVerified,
                    errors = new string[0]
                }));
                model = null; // leave the successfully created/reopened document open
            }
            catch (Exception error)
            {
                string cleanup = "";
                string partialDocument = "";
                if (model != null && app != null)
                {
                    try
                    {
                        partialDocument = PreserveFailedPart(model);
                        cleanup = " Oluşturulan parça inceleme için açık bırakıldı: " + partialDocument
                            + ". İşlem tamamlanmadı; parça otomatik kaydedilmedi.";
                    }
                    catch (Exception failure) { cleanup = " Parça kapatılmadı; inceleme bilgisi alınamadı: " + failure.Message; }
                }
                if (temporary != null)
                {
                    try { if (File.Exists(temporary)) File.Delete(temporary); }
                    catch (Exception failure) { cleanup += " Temporary file cleanup failed: " + failure.Message; }
                }
                if (model == null && app != null && previous != null)
                {
                    try { int code = 0; app.ActivateDoc3(previous, false, (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref code); }
                    catch { }
                }
                Console.WriteLine(Json.Serialize(new { success = false, partial_document = partialDocument,
                    errors = new string[] { lastPhase + ": " + error.Message + cleanup } }));
            }
            finally
            {
                if (preferenceCaptured && app != null)
                {
                    try
                    {
                        app.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swInputDimValOnCreate, inputPreference);
                        if (app.GetUserPreferenceToggle((int)swUserPreferenceToggle_e.swInputDimValOnCreate)!=inputPreference)
                            Console.Error.WriteLine("Original dimension input preference was not restored.");
                    }
                    catch (Exception failure) { Console.Error.WriteLine("Preference restore failed: " + failure.Message); }
                }
                // Releasing this host never calls ExitApp or terminates sldworks.exe.
                if (app != null && Marshal.IsComObject(app)) Marshal.ReleaseComObject(app);
            }
        }
    }

    internal static class ChannelCuts
    {
        // Keep this native construction order aligned with geometry.operation_plan.
        internal static readonly string[] OperationOrder = { "chamfer", "fillet", "groove", "keyway" };
        internal static double KeywayStartMetres(double diameterMm)
        { return (diameterMm / 2 + 1) * .001; }

        internal static bool KeywayReverseDirection(double normalAlignment)
        {
            Host.Need(!Double.IsNaN(normalAlignment) && !Double.IsInfinity(normalAlignment)
                && Math.Abs(Math.Abs(normalAlignment)-1)<1e-8, "Kama kesme yönü radyal değil.");
            // A cut's default direction is OPPOSITE its sketch normal. Start
            // outside the cylinder and cut inward, irrespective of plane handedness.
            return normalAlignment<0;
        }

        internal static void DriveSketchDimension(IDimension dimension,string name,double metres)
        {
            Host.Need(dimension!=null, "Yeni eskiz ölçüsü bulunamadı: "+name);
            // AddDimension2 can return a driven dimension. Explicitly request
            // a driving dimension on OUR new sketch; never delete constraints
            // or accept an uneditable reference as a model input.
            dimension.Name=name;
            if(dimension.DrivenState!=(int)swDimensionDrivenState_e.swDimensionDriving)
                dimension.DrivenState=(int)swDimensionDrivenState_e.swDimensionDriving;
            Host.Need(dimension.DrivenState==(int)swDimensionDrivenState_e.swDimensionDriving,
                "Eskiz ölçüsü sürücü yapılamadı: "+name+". Konumu sabitleyen ilişkiler kontrol edilmeli.");
            Host.Need(dimension.SetSystemValue3(metres,(int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration,null)==0
                && Math.Abs(dimension.SystemValue-metres)<1e-8, "Sürücü ölçü değeri uygulanamadı: "+name);
        }

        internal static void BindKeywayDepth(IFeature feature, double travelMetres)
        {
            // A cut can expose several display dimensions (including sketch
            // dimensions). D1 is the native forward cut-depth parameter; never
            // rename an arbitrary first display dimension or require only one.
            IExtrudeFeatureData2 data=feature.GetDefinition() as IExtrudeFeatureData2;
            Host.Need(data!=null && data.GetEndCondition(true)==(int)swEndConditions_e.swEndCondBlind
                && Math.Abs(data.GetDepth(true)-travelMetres)<1e-8,
                "Kama kör kesme boyu native unsur tanımıyla uyuşmuyor.");
            IDimension dimension=feature.Parameter("D1") as IDimension;
            Host.Need(dimension!=null && dimension.DrivenState==(int)swDimensionDrivenState_e.swDimensionDriving
                && Math.Abs(dimension.SystemValue-travelMetres)<1e-8,
                "Kama ileri kesme derinliği (D1) sürücü ölçüsü doğrulanamadı.");
            dimension.Name="KESME_BOYU";
            Host.Need(dimension.Name=="KESME_BOYU", "Kama kesme boyu ölçüsü adlandırılamadı.");
        }

        internal static double VerifyKeywayFloor(IFeature feature, double diameterMm, double depthMm,
            double[] origin, double[] radial)
        {
            // Measure the evaluated BREP plane, independently of the dimension
            // and its air-clearance allowance. PlaneParams: normal[3], point[3], SI.
            object[] faces=feature.GetFaces() as object[];
            var heights=new List<double>();
            if (faces!=null) foreach(object raw in faces)
            {
                ISurface surface=(ISurface)((IFace2)raw).GetSurface();
                if (surface==null || !surface.IsPlane()) continue;
                double[] p=surface.PlaneParams as double[];
                if(p==null || p.Length!=6) continue;
                double alignment=p[0]*radial[0]+p[1]*radial[1]+p[2]*radial[2];
                if(Math.Abs(Math.Abs(alignment)-1)>1e-8) continue;
                heights.Add((p[3]-origin[0])*radial[0]+(p[4]-origin[1])*radial[1]+(p[5]-origin[2])*radial[2]);
            }
            Host.Need(heights.Count>0, "Kama tabanının düz katı-model yüzeyi bulunamadı.");
            foreach(double height in heights)
                Host.Need(Math.Abs(height-heights[0])<1e-8, "Kama tabanında farklı derinlikte yüzeyler bulundu.");
            double actualMm=diameterMm/2-heights[0]*1000;
            Host.Need(!Double.IsNaN(actualMm) && !Double.IsInfinity(actualMm) && Math.Abs(actualMm-depthMm)<1e-5,
                "Kama katı-model derinliği yanlış. İstenen="+depthMm.ToString("G8",CultureInfo.InvariantCulture)
                +" mm; ölçülen="+actualMm.ToString("G8",CultureInfo.InvariantCulture)+" mm.");
            return actualMm;
        }

        internal static void SelectKeyway(IModelDoc2 model, IFeature feature)
        {
            Host.Need(feature!=null, "Kama kesme eskizi bulunamadı.");
            ISketch sketch=feature.GetSpecificFeature2() as ISketch;
            Host.Need(sketch!=null, "Kama kesme seçimi bir eskiz değil.");
            int open=0, closed=0;
            int status=sketch.CheckFeatureUse((int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_CUTEXTRUDE,
                ref open,ref closed);
            Host.Need(status==(int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_OK && open==0 && closed==1,
                "Kama profili katı kesmeye uygun tek kapalı kontur değil. API durum="+status
                +", açık="+open+", kapalı="+closed+". Kesme uygulanmadı.");
            ISelectionMgr selection=(ISelectionMgr)model.SelectionManager;
            selection.EnableContourSelection=false;
            model.ClearSelection2(true);
            Host.Need(feature.Select2(false,0) && selection.GetSelectedObjectCount2(-1)==1
                && selection.GetSelectedObjectCount2(0)==1, "Kama kesme eskizi tek başına seçilemedi.");
        }

        internal static void SelectGroove(IModelDoc2 model, IFeature sketch, ISketchSegment axis)
        {
            // Use the actual segment created in this sketch, not a display name
            // resolved through SelectByID2. Mark 4 is the cut-revolve axis.
            ISelectionMgr selection = (ISelectionMgr)model.SelectionManager;
            selection.EnableContourSelection = false;
            model.ClearSelection2(true);
            Host.Need(sketch != null && axis != null && axis.ConstructionGeometry,
                "Segman kesme eskizi veya construction ekseni bulunamadı.");
            SelectData data = (SelectData)selection.CreateSelectData();
            data.Mark = 4;
            Host.Need(sketch.Select2(false, 0) && axis.Select4(true, data),
                "Segman kesme eskizi/ekseni seçilemedi (eskiz=0, eksen=4).");
            Host.Need(selection.GetSelectedObjectCount2(-1) == 2
                && selection.GetSelectedObjectCount2(0) == 1
                && selection.GetSelectedObjectCount2(4) == 1,
                "Segman kesme seçimleri doğrulanamadı; yanlış konturla kesme yapılmadı.");
        }

        internal static IFeature Groove(IFeatureManager manager)
        {
            // Dedicated native cut contract: avoids the boss/solid/thin flags
            // of FeatureRevolve2, which returned null in the reported SW session.
            // Still exposed by the installed interop; no mesh/boolean substitute.
            return (IFeature)manager.FeatureRevolveCut2(
                Angle:Math.PI*2, ReverseDir:false, Angle2:0,
                RevType:(int)swRevolveType_e.swRevolveTypeOneDirection360Degrees,
                Options:(int)swRevolveOptions_e.swAutoCloseSketch,
                UseFeatScope:true, UseAutoSelect:true, AssemblyFeatureScope:false,
                AutoSelectComponents:false, PropagateFeatureToParts:false);
        }

        internal static IFeature Fillet(IFeatureManager manager, IEdge edge, double radiusMetres)
        {
            // FeatureFillet3 is obsolete for constant-radius fillets since SW
            // 2020. Initialize the current native definition explicitly.
            ISimpleFilletFeatureData2 data=(ISimpleFilletFeatureData2)manager.CreateDefinition((int)swFeatureNameID_e.swFmFillet);
            Host.Need(data!=null && data.Initialize((int)swSimpleFilletType_e.swConstRadiusFillet),
                "Sabit radyüs tanımı oluşturulamadı.");
            data.CurvatureContinuous=false;
            data.ConicTypeForCrossSectionProfile=(int)swFeatureFilletProfileType_e.swFeatureFilletCircular;
            data.IsMultipleRadius=false;
            data.AsymmetricFillet=false;
            data.DefaultRadius=radiusMetres;
            data.PropagateToTangentFaces=false;
            data.Edges=new object[]{edge};
            return (IFeature)manager.CreateFeature(data);
        }

        internal static ISketchSlot KeywaySlot(ISketchManager manager, double startMetres,
            double lengthMetres, double widthMetres, double axialSign)
        {
            // The API points are the arc centres, not the overall slot tips.
            return (ISketchSlot)manager.CreateSketchSlot(
                (int)swSketchSlotCreationType_e.swSketchSlotCreationType_line,
                (int)swSketchSlotLengthType_e.swSketchSlotLengthType_CenterCenter,
                widthMetres, axialSign*(startMetres+widthMetres/2),0,0,
                axialSign*(startMetres+lengthMetres-widthMetres/2),0,0,
                axialSign*(startMetres+lengthMetres/2),widthMetres/2,0,1,false);
        }

        internal static IFeature Keyway(IFeatureManager manager, double depthMetres, double normalAlignment)
        {
            return (IFeature)manager.FeatureCut4(
                Sd:true, Flip:false, Dir:KeywayReverseDirection(normalAlignment),
                T1:(int)swEndConditions_e.swEndCondBlind, T2:0,
                D1:depthMetres, D2:0, Dchk1:false, Dchk2:false,
                Ddir1:false, Ddir2:false, Dang1:0, Dang2:0,
                OffsetReverse1:false, OffsetReverse2:false,
                TranslateSurface1:false, TranslateSurface2:false, NormalCut:false,
                UseFeatScope:true, UseAutoSelect:true, AssemblyFeatureScope:false,
                AutoSelectComponents:false, PropagateFeatureToParts:false,
                T0:(int)swStartConditions_e.swStartSketchPlane, StartOffset:0,
                FlipStartOffset:false, OptimizeGeometry:false);
        }

        internal static double ExpectedVolume(Stage stage, Operation operation)
        {
            double radius=stage.diameter/2;
            if (operation.kind=="groove")
                return Math.PI*(radius*radius-Math.Pow(radius-operation.depth,2))*operation.width*1e-9;
            // Integrate the capsule footprint through the curved shaft surface.
            // z=a*sin(t) removes the square-root endpoint singularities.
            double half=operation.width/2, sum=0;
            const int slices=256;
            double step=Math.PI/2/slices;
            for (int i=0;i<=slices;i++)
            {
                double t=i*step, cosine=Math.Cos(t), z=half*Math.Sin(t);
                double height=operation.depth-z*z/(radius+Math.Sqrt(radius*radius-z*z));
                double value=(operation.length-operation.width+2*half*cosine)*height*half*cosine;
                sum+=(i==0 || i==slices ? 1 : i%2==0 ? 2 : 4)*value;
            }
            return 2*sum*step/3*1e-9;
        }

        internal static void VerifyRemoval(string name, double before, double after, double expected)
        {
            double removed=before-after;
            Host.Need(expected>0 && !Double.IsNaN(removed) && !Double.IsInfinity(removed)
                && removed>0 && Math.Abs(removed-expected)<=Math.Max(1e-15,expected*1e-5),
                name+": Kesme hacmi doğrulanamadı. Beklenen talaş "+(expected*1e9).ToString("G8",CultureInfo.InvariantCulture)
                +" mm3; ölçülen "+(removed*1e9).ToString("G8",CultureInfo.InvariantCulture)+" mm3.");
        }
    }

    internal sealed class Builder
    {
        private readonly IModelDoc2 model;
        private readonly Project project;
        private readonly IMathUtility math;
        private readonly List<string> lengthNames = new List<string>();
        private readonly List<string> diameterNames = new List<string>();
        private readonly List<string> sketchNames = new List<string>();
        private readonly List<string> equations = new List<string>();
        private readonly Dictionary<string, int> stageIndices = new Dictionary<string, int>();
        private IFeature plane;
        private IMathTransform profileToModel;
        private string activeSketchName;
        private string firstGrooveWidth;
        private string firstKeywayWidth;
        internal readonly List<string> ExpectedNames = new List<string>();
        internal bool ZeroOffsetVerified;

        internal Builder(IModelDoc2 document, Project parameters, IMathUtility mathUtility)
        {
            model = document; project = parameters; math=mathUtility;
            for (int i=0; i<project.stages.Length; i++)
            {
                stageIndices.Add(project.stages[i].id, i);
                string sketch = "MIL_PROFIL_" + (i+1).ToString("00");
                sketchNames.Add(sketch);
                lengthNames.Add("BOY_" + (i+1).ToString("00") + "@" + sketch);
                diameterNames.Add("CAP_" + (i+1).ToString("00") + "@" + sketch);
                ExpectedNames.Add("MIL_ANA_GEOMETRI_" + (i+1).ToString("00"));
            }
            foreach (string kind in ChannelCuts.OperationOrder)
            {
                int index=0;
                foreach (Operation op in project.operations)
                {
                    if (op.kind != kind) continue;
                    string name = OperationName(kind, ++index);
                    ExpectedNames.Add(name);
                    if (kind == "groove" || kind == "keyway") sketchNames.Add(name + "_ESKIZI");
                    if (kind == "groove" && firstGrooveWidth == null) firstGrooveWidth = "GENISLIK@" + name + "_ESKIZI";
                    if (kind == "keyway" && firstKeywayWidth == null) firstKeywayWidth = "GENISLIK@" + name + "_ESKIZI";
                }
            }
        }

        private static string OperationName(string kind, int i)
        {
            string prefix = kind == "groove" ? "SEGMAN_KANALI" : kind == "keyway" ? "KAMA_KANALI" : kind == "chamfer" ? "PAH" : "RADYUS";
            return prefix + "_" + i.ToString("00");
        }
        private static double M(double mm) { return mm * .001; }
        private static string Q(string name) { return "\"" + name + "\""; }
        private static string MM(double value) { return value.ToString("R", CultureInfo.InvariantCulture) + "mm"; }
        private string StartExpression(int stage)
        {
            if (stage == 0) return "0mm";
            var terms = new List<string>();
            for (int i=0; i<stage; i++) terms.Add(Q(lengthNames[i]));
            return String.Join(" + ", terms.ToArray());
        }
        private double Start(int stage)
        { double x=0; for (int i=0;i<stage;i++) x+=project.stages[i].length; return x; }

        private void Equation(string left, string expression)
        { equations.Add(Q(left) + " = " + expression); }
        private void Global(string name, double value)
        { equations.Add(Q(name) + " = " + MM(value)); }
        private void ApplyEquations()
        {
            if (equations.Count==0) return;
            IEquationMgr manager = (IEquationMgr)model.GetEquationMgr();
            foreach (string equation in equations)
                Host.Need(manager.Add2(-1, equation, false) >= 0, "Equation failed: " + equation);
            manager.EvaluateAll();
            // Official EvaluateAll returns -1 on BOTH success and failure.
            // Read each equation and its Status instead of trusting that code.
            for (int i=0;i<manager.GetCount();i++)
            {
                double value=manager.Value[i];
                Host.Need(manager.Status>=0 && !Double.IsNaN(value) && !Double.IsInfinity(value),
                    "Equation did not evaluate: " + manager.Equation[i]);
            }
            equations.Clear();
        }

        private ISketch BeginSketch(string name, IFeature support = null)
        {
            ((ISelectionMgr)model.SelectionManager).EnableContourSelection=false;
            model.ClearSelection2(true); Host.Need((support ?? plane).Select2(false,0), "Reference plane selection failed.");
            model.SketchManager.InsertSketch(true);
            ISketch sketch = (ISketch)model.SketchManager.ActiveSketch;
            Host.Need(sketch != null, "Sketch could not be opened.");
            IFeature feature = (IFeature)model.Extension.GetLastFeatureAdded();
            Host.Need(feature != null && feature.GetSpecificFeature2() is ISketch, "New sketch feature was not found.");
            feature.Name = name;
            Host.Need(feature.Name==name, "Sketch name is already in use in the Part template: " + name);
            activeSketchName = name;
            model.SketchManager.AddToDB = true;
            return sketch;
        }
        private void EndSketch(ISketch sketch)
        {
            model.SketchManager.AddToDB = false;
            model.ClearSelection2(true);
            // No blanket fixing or automatic coordinate dimensions: only the
            // datum point is fixed. All geometry has explicit driving dimensions.
            Host.Need(sketch.GetConstrainedStatus() == (int)swConstrainedStatus_e.swFullyConstrained,
                "Sketch is not fully constrained: " + activeSketchName);
            model.SketchManager.InsertSketch(true);
            // Register renamed sketch dimensions before adding equations.
            Rebuild();
            ApplyEquations(); Rebuild();
        }
        private void Coincident(ISketchPoint a, ISketchPoint b)
        {
            Array x = (Array)a.GetID(); Array y = (Array)b.GetID();
            if (Convert.ToInt32(x.GetValue(0)) == Convert.ToInt32(y.GetValue(0)) && Convert.ToInt32(x.GetValue(1)) == Convert.ToInt32(y.GetValue(1))) return;
            model.ClearSelection2(true);
            Host.Need(a.Select4(false,null) && b.Select4(true,null), "Sketch point selection failed.");
            model.SketchAddConstraints("sgCOINCIDENT");
        }
        private ISketchSegment Line(double x1, double y1, double x2, double y2, bool construction)
        {
            model.SketchManager.AddToDB = true;
            ISketchSegment segment = (ISketchSegment)model.SketchManager.CreateLine(M(x1),M(y1),0,M(x2),M(y2),0);
            Host.Need(segment != null, "Sketch line creation failed."); segment.ConstructionGeometry = construction;
            model.SketchManager.AddToDB = false;
            Host.Need(segment.Select4(false,null), "Sketch line selection failed.");
            model.SketchAddConstraints(y1 == y2 ? "sgHORIZONTAL" : "sgVERTICAL");
            return segment;
        }
        private static ISketchPoint StartPoint(ISketchSegment segment) { return (ISketchPoint)((ISketchLine)segment).GetStartPoint2(); }
        private static ISketchPoint EndPoint(ISketchSegment segment) { return (ISketchPoint)((ISketchLine)segment).GetEndPoint2(); }
        private IDimension Dimension(ISketchSegment segment, string name, double value, double x, double y, bool diameter)
        {
            model.ClearSelection2(true); Host.Need(segment.Select4(false,null), "Dimension segment selection failed.");
            IDisplayDimension display = (IDisplayDimension)(diameter ? model.AddDiameterDimension2(M(x),M(y),0) : model.AddDimension2(M(x),M(y),0));
            Host.Need(display != null, "Driving dimension could not be created: " + name);
            IDimension dimension = (IDimension)display.GetDimension2(0);
            ChannelCuts.DriveSketchDimension(dimension,name,M(value));
            return dimension;
        }

        private ISketchPoint Origin()
        {
            model.SketchManager.AddToDB = true;
            ISketchPoint point = (ISketchPoint)model.SketchManager.CreatePoint(0,0,0);
            model.SketchManager.AddToDB = false;
            Host.Need(point != null && point.Select4(false,null), "Sketch datum creation failed.");
            model.SketchAddConstraints("sgFIXED");
            return point;
        }
        private ISketchSegment[] Rectangle(string sketch, ISketchPoint origin, double x, double y, double width, double height,
            string widthName, string heightName, string xExpression, string yExpression, string heightExpression, bool movableX = false)
        {
            // Dimension the position datum BEFORE creating the profile. Later
            // profile coincidences must consume this position, not make its
            // BASLANGIC dimension a redundant reference on a prior stage edge.
            ISketchPoint anchor=origin;
            if (movableX)
            {
                // A datum below/outside the part keeps both location dimensions
                // positive even at offset=0. No zero-length line or zero driving
                // dimension; the editable *_KONUM global still starts at 0 mm.
                model.SketchManager.AddToDB = true;
                ISketchPoint datum = (ISketchPoint)model.SketchManager.CreatePoint(M(-1),M(-1),0);
                model.SketchManager.AddToDB = false;
                Host.Need(datum != null && datum.Select4(false,null), "Channel datum creation failed.");
                model.SketchAddConstraints("sgFIXED");
                ISketchSegment horizontal = Line(-1,-1,x,-1,true);
                Coincident(StartPoint(horizontal),datum);
                Dimension(horizontal,"BASLANGIC",x+1,x/2,-6,false);
                Equation("BASLANGIC@"+sketch,"("+xExpression+") + 1mm");
                ISketchSegment vertical = Line(x,-1,x,y,true);
                Coincident(StartPoint(vertical),EndPoint(horizontal));
                Dimension(vertical,"KONUM_Y",y+1,x-5,y/2,false);
                Equation("KONUM_Y@"+sketch,"("+yExpression+") + 1mm");
                anchor = EndPoint(vertical);
            }
            else if (x > 0)
            {
                ISketchSegment rail=Line(0,0,x,0,true); Coincident(StartPoint(rail),origin);
                anchor=EndPoint(rail); Dimension(rail,"BASLANGIC",x,x/2,-5,false);
                if (xExpression != null) Equation("BASLANGIC@"+sketch,xExpression);
            }
            if (y > 0 && !movableX)
            {
                ISketchSegment rail=Line(x,0,x,y,true); Coincident(StartPoint(rail),anchor);
                anchor=EndPoint(rail); Dimension(rail,"KONUM_Y",y,x-5,y/2,false);
                if (yExpression != null) Equation("KONUM_Y@"+sketch,yExpression);
            }
            ISketchSegment[] lines = new ISketchSegment[] {
                Line(x,y,x+width,y,false), Line(x+width,y,x+width,y+height,false),
                Line(x+width,y+height,x,y+height,false), Line(x,y+height,x,y,false)
            };
            for (int i=0;i<4;i++) Coincident(EndPoint(lines[i]),StartPoint(lines[(i+1)%4]));
            Coincident(StartPoint(lines[0]),anchor);
            Dimension(lines[0],widthName,width,x+width/2,y-5,false);
            if (heightName!=null) Dimension(lines[1],heightName,height,x+width+5,y+height/2,false);
            if (heightExpression != null) Equation(heightName+"@"+sketch,heightExpression);
            return lines;
        }
        private void SelectSketch(string sketch)
        {
            model.ClearSelection2(true);
            // Do not inherit contour-picking mode from the preceding feature.
            ((ISelectionMgr)model.SelectionManager).EnableContourSelection=false;
            Host.Need(model.Extension.SelectByID2(sketch,"SKETCH",0,0,0,false,0,null,0), "Sketch selection failed: "+sketch);
        }
        private void SelectRevolve(string sketch, string axis, int axisMark = 16)
        {
            SelectSketch(sketch);
            // Official FeatureRevolve2: sketch mark 0; axis mark 4 OR 16.
            Host.Need(model.Extension.SelectByID2(axis,"EXTSKETCHSEGMENT",0,0,0,true,axisMark,null,0), "Revolve axis selection failed.");
        }
        private void Named(IFeature feature, string name)
        {
            Host.Need(feature != null, "Native feature failed: " + name);
            feature.Name = name; Host.Need(feature.Name == name, "Feature name was not assigned: " + name);
            Rebuild();
        }
        private void Rebuild()
        { Host.Need(model.EditRebuild3() && model.ForceRebuild3(false), "SOLIDWORKS rebuild failed."); }

        internal void Build()
        {
            object[] initial = (object[])((IPartDoc)model).GetBodies2((int)swBodyType_e.swSolidBody,false);
            Host.Need(initial == null || initial.Length == 0, "Default Part template contains solid geometry.");
            // Select by feature type, never localized Front Plane/Ön Düzlem names.
            for (IFeature f=(IFeature)model.FirstFeature();f!=null;f=(IFeature)f.GetNextFeature())
                if (f.GetTypeName2()=="RefPlane") { plane=f; break; }
            Host.Need(plane != null, "No base reference plane found in the Part template.");
            for (int i=0;i<project.stages.Length;i++)
            {
                Host.Report("Kademe " + (i+1) + "/" + project.stages.Length + " oluşturuluyor");
                BuildStage(i);
            }
            foreach (string kind in ChannelCuts.OperationOrder)
            {
                int count=0;
                foreach (Operation op in project.operations)
                {
                    if (op.kind != kind) continue;
                    string name=OperationName(kind,++count);
                    Host.Report(name + " oluşturuluyor");
                    if (kind=="groove") BuildGroove(op,name);
                    else if (kind=="keyway") BuildKeyway(op,name);
                    else if (kind=="chamfer") BuildChamfer(op,name);
                    else BuildFillet(op,name);
                }
            }
            Verify();
        }
        private void BuildStage(int i)
        {
            Stage stage=project.stages[i]; string sketch="MIL_PROFIL_"+(i+1).ToString("00");
            ISketch drawing=BeginSketch(sketch); ISketchPoint origin=Origin();
            if (i==0) profileToModel=drawing.ModelToSketchTransform.IInverse();
            model.SketchManager.AddToDB=true;
            ISketchSegment circle=(ISketchSegment)model.SketchManager.CreateCircleByRadius(M(Start(i)),0,0,M(stage.diameter/2));
            Host.Need(circle!=null,"Diameter construction circle failed."); circle.ConstructionGeometry=true;
            model.SketchManager.AddToDB=false;
            Dimension(circle,"CAP_"+(i+1).ToString("00"),stage.diameter,-8,stage.diameter/2,true);
            ISketchSegment[] rectangle=Rectangle(sketch,origin,Start(i),0,stage.length,stage.diameter/2,
                "BOY_"+(i+1).ToString("00"),null,StartExpression(i),null,null);
            Coincident((ISketchPoint)((ISketchArc)circle).GetCenterPoint2(),StartPoint(rectangle[0]));
            // The vertical side meets the diameter-driving circle directly.
            // Do not depend on an immediately solved CAP/2 dimension equation.
            model.ClearSelection2(true);
            Host.Need(StartPoint(rectangle[3]).Select4(false,null) && circle.Select4(true,null),
                "Diameter/profile constraint selection failed.");
            model.SketchAddConstraints("sgCOINCIDENT");
            string axis=rectangle[0].GetName()+"@"+sketch;
            EndSketch(drawing); SelectRevolve(sketch,axis);
            IFeature feature=(IFeature)model.FeatureManager.FeatureRevolve2(true,true,false,false,false,false,
                0,0,Math.PI*2,0,false,false,0,0,0,0,0,true,true,true);
            Named(feature,"MIL_ANA_GEOMETRI_"+(i+1).ToString("00"));
        }
        private ISketchSegment BuildChannel(Operation op, string name)
        {
            int i=stageIndices[op.stage_id]; Stage stage=project.stages[i]; string sketch=name+"_ESKIZI";
            string offset=name+"_KONUM"; string depth=name+"_DERINLIK";
            Global(offset,op.offset); Global(depth,op.depth);
            ISketch drawing=BeginSketch(sketch); ISketchPoint origin=Origin();
            // Each groove owns its axis, independent of consumed boss sketches.
            ISketchSegment centerline=Line(0,0,1,0,true);
            Coincident(StartPoint(centerline),origin);
            Dimension(centerline,"EKSEN_BOYU",1,.5,-2,false);
            // +1 mm clearance lies outside the cylinder and follows CAP on rebuild.
            Rectangle(sketch,origin,Start(i)+op.offset,stage.diameter/2-op.depth,
                op.width,op.depth+1,"GENISLIK","KESICI_YUKSEKLIK",
                StartExpression(i)+" + "+Q(offset), Q(diameterNames[i])+" / 2 - "+Q(depth), Q(depth)+" + 1mm",true);
            EndSketch(drawing);
            return centerline;
        }
        private void RequireSingleCutBody()
        {
            object[] bodies=(object[])((IPartDoc)model).GetBodies2((int)swBodyType_e.swSolidBody,false);
            Host.Need(bodies!=null && bodies.Length==1,"Kanal kesmeden önce mil tek katı gövde olmalı.");
        }
        private void BuildGroove(Operation op,string name)
        {
            RequireSingleCutBody(); double before=Volume();
            ISketchSegment axis=BuildChannel(op,name);
            Host.Report(name+": 360° döndürerek kesme uygulanıyor");
            ChannelCuts.SelectGroove(model,Find(name+"_ESKIZI"),axis);
            IFeature cut=ChannelCuts.Groove(model.FeatureManager);
            Host.Need(cut!=null,"Segman kesimi oluşturulamadı (FeatureRevolveCut2). Eskiz ve eksen seçildi; kesme tamamlanmadı.");
            Named(cut,name);
            ChannelCuts.VerifyRemoval(name,before,Volume(),ChannelCuts.ExpectedVolume(project.stages[stageIndices[op.stage_id]],op));
        }
        private void BuildKeyway(Operation op,string name)
        {
            RequireSingleCutBody(); double before=Volume();
            int i=stageIndices[op.stage_id]; Stage stage=project.stages[i];
            string sketch=name+"_ESKIZI", offset=name+"_KONUM", depth=name+"_DERINLIK", length=name+"_BOY";
            Global(offset,op.offset); Global(depth,op.depth); Global(length,op.length);
            IFeature startPlane=KeywayStartPlane(name,stage.diameter/2+1,i);
            ISketch drawing=BeginSketch(sketch,startPlane);
            IMathTransform toSketch=drawing.ModelToSketchTransform;
            // MathPoint/MathTransform consume SI metres, unlike our mm model.
            double[] startOrigin=Point(0,ChannelCuts.KeywayStartMetres(stage.diameter),0,profileToModel);
            double[] localOrigin=Point(startOrigin,toSketch);
            Host.Need(Math.Abs(localOrigin[0])+Math.Abs(localOrigin[1])+Math.Abs(localOrigin[2])<1e-8,
                "Kama eskiz orijini dış kesme düzlemiyle uyuşmuyor.");
            double[] localAxis=Vector(Vector(1,0,0,profileToModel),toSketch);
            Host.Need(Math.Abs(Math.Abs(localAxis[0])-1)<1e-8,"Kama düzleminin X ekseni mil eksenine paralel değil.");
            double sign=localAxis[0]>0 ? 1 : -1;
            double x=Start(i)+op.offset, center=x+op.width/2;
            model.SketchManager.AddToDB=false;
            ISketchSlot slot=ChannelCuts.KeywaySlot(model.SketchManager,M(x),M(op.length),M(op.width),sign);
            Host.Need(slot!=null,"Kapsül kama profili oluşturulamadı.");
            Host.Need(Math.Abs(slot.Width-M(op.width))<1e-8 && Math.Abs(slot.Length-M(op.length-op.width))<1e-8,
                "Kama slotunun toplam boyu veya genişliği beklenen ölçüde değil.");
            ISketchSegment axis=null, arc=null;
            foreach (object raw in (object[])drawing.GetSketchSegments())
            {
                ISketchSegment segment=(ISketchSegment)raw;
                if (segment.ConstructionGeometry && segment.GetType()==(int)swSketchSegments_e.swSketchLINE) axis=segment;
                if (!segment.ConstructionGeometry && segment.GetType()==(int)swSketchSegments_e.swSketchARC) arc=segment;
            }
            Host.Need(axis!=null && arc!=null,"Kama slotunun ekseni veya uç yayı bulunamadı.");
            Horizontal(axis);
            Dimension(arc,"GENISLIK",op.width,sign*(x+op.length),op.width,true);
            Dimension(axis,"MERKEZLER_ARASI",op.length-op.width,sign*(x+op.length/2),-op.width,false);
            Equation("MERKEZLER_ARASI@"+sketch,Q(length)+" - "+Q("GENISLIK@"+sketch));
            // Keep the position dimension positive, including an overall offset of zero.
            model.SketchManager.AddToDB=true;
            ISketchPoint datum=(ISketchPoint)model.SketchManager.CreatePoint(M(-sign),0,0);
            model.SketchManager.AddToDB=false;
            Host.Need(datum!=null && datum.Select4(false,null),"Kama konum datumu oluşturulamadı.");
            model.SketchAddConstraints("sgFIXED");
            ISketchSegment rail=Line(-sign,0,sign*center,0,true);
            Coincident(StartPoint(rail),datum);
            ISketchPoint a=StartPoint(axis), b=EndPoint(axis);
            Coincident(EndPoint(rail),sign*a.X<sign*b.X ? a : b);
            Dimension(rail,"BASLANGIC",center+1,sign*center/2,-op.width-5,false);
            Equation("BASLANGIC@"+sketch,StartExpression(i)+" + "+Q(offset)+" + "+Q("GENISLIK@"+sketch)+" / 2 + 1mm");
            double alignment=Dot(Vector(0,0,1,toSketch.IInverse()),Vector(0,1,0,profileToModel));
            EndSketch(drawing);
            Host.Report(name+": mil dışından tabana kör kesme uygulanıyor (derinlik="
                +op.depth.ToString("G8",CultureInfo.InvariantCulture)+" mm)");
            ChannelCuts.SelectKeyway(model,Find(sketch));
            // The sketch lies 1 mm outside the cylinder; depth + 1 mm ends
            // exactly on R-depth. Never flip to an unverified opposite cut.
            IFeature cut=ChannelCuts.Keyway(model.FeatureManager,M(op.depth+1),alignment);
            Host.Need(cut!=null,"Kama kesimi oluşturulamadı (FeatureCut4). Kapalı eskiz seçildi; mil dışından tabana kesme tamamlanmadı."
                +" Çap="+stage.diameter.ToString("G8",CultureInfo.InvariantCulture)
                +" mm; boy="+op.length.ToString("G8",CultureInfo.InvariantCulture)
                +" mm; genişlik="+op.width.ToString("G8",CultureInfo.InvariantCulture)
                +" mm; derinlik="+op.depth.ToString("G8",CultureInfo.InvariantCulture)
                +" mm; normal="+alignment.ToString("G8",CultureInfo.InvariantCulture)+".");
            Named(cut,name);
            ChannelCuts.BindKeywayDepth(cut,M(op.depth+1));
            Equation("KESME_BOYU@"+name,Q(depth)+" + 1mm");
            ApplyEquations(); Rebuild();
            double actualDepth=ChannelCuts.VerifyKeywayFloor(cut,stage.diameter,op.depth,
                Point(0,0,0,profileToModel),Vector(0,1,0,profileToModel));
            Host.Report(name+": katı modelde kama derinliği doğrulandı ("
                +actualDepth.ToString("G8",CultureInfo.InvariantCulture)+" mm)");
            model.ClearSelection2(true); startPlane.Select2(false,0); model.BlankRefGeom();
            ChannelCuts.VerifyRemoval(name,before,Volume(),ChannelCuts.ExpectedVolume(project.stages[stageIndices[op.stage_id]],op));
        }

        private double[] Vector(double x,double y,double z,IMathTransform transform)
        { return Vector(new double[]{x,y,z},transform); }
        private double[] Vector(double[] value,IMathTransform transform)
        { return (double[])((IMathVector)((IMathVector)math.CreateVector(value)).MultiplyTransform(transform)).ArrayData; }
        private double[] Point(double x,double y,double z,IMathTransform transform)
        { return Point(new double[]{x,y,z},transform); }
        private double[] Point(double[] value,IMathTransform transform)
        { return (double[])((IMathPoint)((IMathPoint)math.CreatePoint(value)).MultiplyTransform(transform)).ArrayData; }
        private static double Dot(double[] a,double[] b)
        { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
        private void Horizontal(ISketchSegment segment)
        {
            object[] relations=(object[])segment.GetRelations();
            if (relations!=null) foreach (object raw in relations)
                if (((ISketchRelation)raw).GetRelationType()==(int)swConstraintType_e.swConstraintType_HORIZONTAL) return;
            model.ClearSelection2(true);
            Host.Need(segment.Select4(false,null),"Kama ekseni seçilemedi.");
            model.SketchAddConstraints("sgHORIZONTAL");
        }
        private void RenameOnlyDimension(IFeature feature,string name,double value)
        {
            IDisplayDimension display=(IDisplayDimension)feature.GetFirstDisplayDimension();
            Host.Need(display!=null && feature.GetNextDisplayDimension(display)==null,"Tek sürücü ölçü bekleniyor: "+feature.Name);
            IDimension dimension=(IDimension)display.GetDimension2(0);
            Host.Need(dimension.DrivenState==(int)swDimensionDrivenState_e.swDimensionDriving
                && Math.Abs(dimension.SystemValue-M(value))<1e-8,"Geçersiz sürücü ölçü: "+feature.Name);
            dimension.Name=name;
        }
        private IFeature KeywayStartPlane(string name,double height,int stage)
        {
            double[] radial=Vector(0,1,0,profileToModel), axial=Vector(1,0,0,profileToModel);
            double[] origin=Point(0,0,0,profileToModel);
            IFeature support=null; double direction=0;
            for (IFeature f=(IFeature)model.FirstFeature();f!=null;f=(IFeature)f.GetNextFeature())
            {
                if (f.GetTypeName2()!="RefPlane") continue;
                IMathTransform transform=((IRefPlane)f.GetSpecificFeature2()).Transform;
                double alignment=Dot(Vector(0,0,1,transform),radial);
                double[] p=Point(0,0,0,transform);
                double distance=Dot(new double[]{p[0]-origin[0],p[1]-origin[1],p[2]-origin[2]},radial);
                if (Math.Abs(Math.Abs(alignment)-1)<1e-8 && Math.Abs(distance)<1e-8
                    && Math.Abs(Math.Abs(Dot(Vector(1,0,0,transform),axial))-1)<1e-8)
                { support=f; direction=alignment; break; }
            }
            Host.Need(support!=null,"Mil ekseninden geçen radyal kama düzlemi bulunamadı.");
            model.ClearSelection2(true); Host.Need(support.Select2(false,0),"Kama referans düzlemi seçilemedi.");
            int constraint=(int)swRefPlaneReferenceConstraints_e.swRefPlaneReferenceConstraint_Distance;
            if (direction<0) constraint|=(int)swRefPlaneReferenceConstraints_e.swRefPlaneReferenceConstraint_OptionFlip;
            Host.Need(model.FeatureManager.InsertRefPlane(constraint,M(height),0,0,0,0)!=null,"Kama dış kesme düzlemi oluşturulamadı.");
            IFeature startPlane=(IFeature)model.Extension.GetLastFeatureAdded();
            Host.Need(startPlane!=null && startPlane.GetSpecificFeature2() is IRefPlane,"Kama dış kesme düzlemi bulunamadı.");
            Named(startPlane,name+"_KESME_DUZLEMI");
            RenameOnlyDimension(startPlane,"KESME_Y",height);
            Equation("KESME_Y@"+startPlane.Name,Q(diameterNames[stage])+" / 2 + 1mm");
            ApplyEquations(); Rebuild();
            double[] actual=Point(0,0,0,((IRefPlane)startPlane.GetSpecificFeature2()).Transform);
            Host.Need(Math.Abs(Dot(new double[]{actual[0]-origin[0],actual[1]-origin[1],actual[2]-origin[2]},radial)-M(height))<1e-8,
                "Kama dış kesme düzlemi milin yanlış tarafında.");
            return startPlane;
        }
        private IEdge SelectCircularEdge(Operation op,int mark)
        {
            int index=stageIndices[op.stage_id]; Stage stage=project.stages[index];
            double x=M(Start(index)+(op.edge=="right"?stage.length:0)); double radius=M(stage.diameter/2);
            double[] centre=Point(x,0,0,profileToModel), direction=Vector(1,0,0,profileToModel);
            var matches=new List<IEdge>();
            object[] bodies=(object[])((IPartDoc)model).GetBodies2((int)swBodyType_e.swSolidBody,false);
            Host.Need(bodies!=null && bodies.Length==1,"A single solid body is required.");
            foreach (object raw in (object[])((IBody2)bodies[0]).GetEdges())
            {
                IEdge edge=(IEdge)raw; ICurve curve=(ICurve)edge.GetCurve();
                if (!curve.IsCircle()) continue;
                double[] p=(double[])curve.CircleParams;
                if (Math.Abs(p[0]-centre[0])<1e-8 && Math.Abs(p[1]-centre[1])<1e-8 && Math.Abs(p[2]-centre[2])<1e-8
                    && Math.Abs(Math.Abs(Dot(new double[]{p[3],p[4],p[5]},direction))-1)<1e-8 && Math.Abs(p[6]-radius)<1e-8)
                    matches.Add(edge);
            }
            Host.Need(matches.Count==1,"Requested circular edge is missing or ambiguous. Operations may intersect.");
            model.ClearSelection2(true);
            ((ISelectionMgr)model.SelectionManager).EnableContourSelection=false;
            SelectData data=(SelectData)((ISelectionMgr)model.SelectionManager).CreateSelectData(); data.Mark=mark;
            Host.Need(((IEntity)matches[0]).Select4(false,data),"Circular edge selection failed.");
            return matches[0];
        }
        private void BuildChamfer(Operation op,string name)
        {
            SelectCircularEdge(op,0);
            Named((IFeature)model.FeatureManager.InsertFeatureChamfer(0,(int)swChamferType_e.swChamferAngleDistance,
                M(op.distance),Math.PI/4,0,0,0,0),name);
        }
        private void BuildFillet(Operation op,string name)
        {
            IEdge edge=SelectCircularEdge(op,1);
            Named(ChannelCuts.Fillet(model.FeatureManager,edge,M(op.radius)),name);
        }

        private IFeature Find(string name)
        {
            return (IFeature)((IPartDoc)model).FeatureByName(name);
        }
        internal void Verify()
        {
            Rebuild();
            object[] bodies=(object[])((IPartDoc)model).GetBodies2((int)swBodyType_e.swSolidBody,false);
            Host.Need(bodies!=null && bodies.Length==1,"Part is not one merged solid body.");
            foreach (string name in ExpectedNames)
            {
                IFeature feature=Find(name); Host.Need(feature!=null,"Missing native feature: "+name);
                string type=feature.GetTypeName2();
                if (type=="ICE") type=feature.GetTypeName();
                bool accepted=name.StartsWith("MIL_ANA_GEOMETRI_") ? type=="Rev" || type=="Revolution" :
                    name.StartsWith("SEGMAN_KANALI_") ? type=="RevCut" :
                    name.StartsWith("KAMA_KANALI_") ? type=="Cut" :
                    name.StartsWith("PAH_") ? type=="Chamfer" : type=="Fillet";
                Host.Need(accepted,"Unexpected native feature type for "+name+": "+type);
                bool warning; int code=feature.GetErrorCode2(out warning);
                Host.Need(code==0,"Feature has a rebuild error or warning: "+name+" ("+code+")");
            }
            foreach (string name in sketchNames)
            {
                IFeature feature=Find(name); Host.Need(feature!=null,"Missing sketch: "+name);
                ISketch sketch=(ISketch)feature.GetSpecificFeature2();
                Host.Need(sketch!=null && sketch.GetConstrainedStatus()==(int)swConstrainedStatus_e.swFullyConstrained,
                    "Sketch is not fully constrained: "+name);
            }
            foreach (string name in diameterNames)
            {
                IDimension dimension=(IDimension)model.Parameter(name);
                Host.Need(dimension!=null && dimension.DrivenState==(int)swDimensionDrivenState_e.swDimensionDriving,
                    "Missing driving diameter: "+name);
            }
            foreach (string name in lengthNames)
            {
                IDimension dimension=(IDimension)model.Parameter(name);
                Host.Need(dimension!=null && dimension.DrivenState==(int)swDimensionDrivenState_e.swDimensionDriving,
                    "Missing driving length: "+name);
            }
            Host.Need(Volume()>0,"Part volume is zero.");
        }
        internal double Volume()
        {
            model.ClearSelection2(true);
            IMassProperty mass=(IMassProperty)model.Extension.CreateMassProperty();
            Host.Need(mass!=null,"Mass properties unavailable.");
            mass.UseSystemUnits=true;
            return mass.Volume;
        }
        private void EditProbe(string name, double factor = 1.01)
        {
            IDimension dimension=(IDimension)model.Parameter(name); Host.Need(dimension!=null,"Edit probe dimension missing: "+name);
            double original=dimension.SystemValue; double before=Volume();
            try
            {
                Host.Need(dimension.SetSystemValue3(original*factor,(int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration,null)==0,"Edit probe failed.");
                Verify(); Host.Need(Math.Abs(Volume()-before)>Math.Max(1e-16,before*1e-8),"Native dimension edit did not change geometry: "+name);
            }
            finally
            {
                Host.Need(dimension.SetSystemValue3(original,(int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration,null)==0,"Edit probe restore failed.");
                Verify();
            }
            Host.Need(Math.Abs(Volume()-before)<Math.Max(1e-15,before*1e-8),"Restored geometry differs.");
        }
        internal void VerifyEditable()
        {
            Host.Report("Driving ölçüler değiştiriliyor ve rebuild doğrulanıyor");
            EditProbe(diameterNames[0]); EditProbe(lengthNames[0]);
            if (firstGrooveWidth!=null) EditProbe(firstGrooveWidth);
            if (firstKeywayWidth!=null) EditProbe(firstKeywayWidth,.99);
            foreach (string kind in new string[] { "groove", "keyway" })
            {
                int count=0;
                foreach (Operation op in project.operations)
                {
                    if (op.kind!=kind) continue;
                    string name=OperationName(kind,++count);
                    if (op.offset!=0) continue;
                    IEquationMgr manager=(IEquationMgr)model.GetEquationMgr();
                    int equationIndex=-1;
                    for (int i=0;i<manager.GetCount();i++)
                        if (manager.Equation[i].Split('=')[0].Trim()==Q(name+"_KONUM")) { equationIndex=i;break; }
                    Host.Need(equationIndex>=0,"Zero offset global is missing.");
                    string original=manager.Equation[equationIndex];
                    IDimension location=(IDimension)model.Parameter("BASLANGIC@"+name+"_ESKIZI");
                    Host.Need(location!=null,"Zero offset driving location is missing.");
                    double before=location.SystemValue;
                    try
                    {
                        manager.Equation[equationIndex]=Q(name+"_KONUM")+" = 0.1mm";
                        manager.EvaluateAll();Verify();
                        Host.Need(Math.Abs(location.SystemValue-before-M(.1))<1e-9,"Zero offset edit did not move the channel.");
                    }
                    finally
                    {
                        manager.Equation[equationIndex]=original;manager.EvaluateAll();Verify();
                    }
                    Host.Need(Math.Abs(location.SystemValue-before)<1e-9,"Channel position restore failed.");
                    ZeroOffsetVerified=true;
                }
            }
        }
    }
}
