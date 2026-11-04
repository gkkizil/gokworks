// Native SOLIDWORKS drawing for a GOKWORKS shaft part. Separate from ShaftHost.cs:
// the part host builds geometry, this host only reads the saved part and creates
// a NEW .SLDDRW with reference (driven) dimensions and annotations. The part is
// opened read-only and its driving dimensions are verified before and after.
// Compiled on Windows against the running installation's interop assemblies.
using System;
using System.Collections;
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
    internal sealed class AxialCircle { public double X; public double R; public IEdge Edge; }
    internal sealed class AxisLine { public double Y; public double Z; public double X0; public double X1; public IEdge Edge; }
    internal sealed class FloorArc { public double X; public double Y; public double R; public IEdge Edge; }

    internal sealed class Shaft
    {
        // Model frame of the GOKWORKS profile sketch (metres): origin on the axis at the
        // left end face, X along the axis, Y radial (keyway side), Z the profile normal.
        internal double[] Origin, Axis, Radial, Normal;
        internal readonly List<AxialCircle> Circles = new List<AxialCircle>();
        internal readonly List<AxisLine> Lines = new List<AxisLine>();
        internal readonly List<FloorArc> Arcs = new List<FloorArc>();
        internal readonly List<IFace2> Faces = new List<IFace2>();
        internal IBody2 Body;

        internal static double Dot(double[] a, double[] b) { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
        internal static double[] Sub(double[] a, double[] b) { return new double[] { a[0]-b[0], a[1]-b[1], a[2]-b[2] }; }
        internal double AxialMm(double[] p) { return Dot(Sub(p, Origin), Axis) * 1000; }
        internal double RadialMm(double[] p) { return Dot(Sub(p, Origin), Radial) * 1000; }
        internal double NormalMm(double[] p) { return Dot(Sub(p, Origin), Normal) * 1000; }
        internal double[] ModelPoint(double xMm, double yMm, double zMm)
        {
            double[] r = new double[3];
            for (int i = 0; i < 3; i++) r[i] = Origin[i] + (Axis[i]*xMm + Radial[i]*yMm + Normal[i]*zMm) * .001;
            return r;
        }

        internal Shaft(IModelDoc2 part)
        {
            IFeature profile = (IFeature)((IPartDoc)part).FeatureByName("MIL_PROFIL_01");
            DrawingHost.Need(profile != null, "MIL_PROFIL_01 eskizi bulunamadı; parça GOKWORKS mil modülüyle oluşturulmamış.");
            ISketch sketch = (ISketch)profile.GetSpecificFeature2();
            IMathTransform toModel = sketch.ModelToSketchTransform.IInverse();
            IMathUtility math = DrawingHost.MathUtility;
            Origin = Point(math, toModel, 0, 0, 0);
            Axis = Unit(Sub(Point(math, toModel, 1, 0, 0), Origin));
            Radial = Unit(Sub(Point(math, toModel, 0, 1, 0), Origin));
            Normal = Unit(Sub(Point(math, toModel, 0, 0, 1), Origin));
            object[] bodies = (object[])((IPartDoc)part).GetBodies2((int)swBodyType_e.swSolidBody, true);
            DrawingHost.Need(bodies != null && bodies.Length == 1, "Parçada tek katı gövde bekleniyor.");
            Body = (IBody2)bodies[0];
            foreach (object raw in (object[])Body.GetEdges())
            {
                IEdge edge = (IEdge)raw; ICurve curve = (ICurve)edge.GetCurve();
                if (curve.IsCircle())
                {
                    double[] p = (double[])curve.CircleParams; // centre(3), axis(3), radius
                    double[] centre = { p[0], p[1], p[2] }, normal = { p[3], p[4], p[5] };
                    double offAxis = Math.Abs(RadialMm(centre)) + Math.Abs(NormalMm(centre));
                    if (offAxis < 1e-4 && Math.Abs(Math.Abs(Dot(normal, Axis)) - 1) < 1e-6)
                        Circles.Add(new AxialCircle { X = AxialMm(centre), R = p[6] * 1000, Edge = edge });
                    else if (Math.Abs(Math.Abs(Dot(normal, Radial)) - 1) < 1e-6)
                        Arcs.Add(new FloorArc { X = AxialMm(centre), Y = RadialMm(centre), R = p[6] * 1000, Edge = edge });
                }
                else if (curve.IsLine())
                {
                    double[] a = (double[])((IVertex)edge.GetStartVertex()).GetPoint();
                    double[] b = (double[])((IVertex)edge.GetEndVertex()).GetPoint();
                    double[] d = Unit(Sub(b, a));
                    if (Math.Abs(Math.Abs(Dot(d, Axis)) - 1) < 1e-6)
                        Lines.Add(new AxisLine { Y = RadialMm(a), Z = NormalMm(a), X0 = Math.Min(AxialMm(a), AxialMm(b)),
                                                 X1 = Math.Max(AxialMm(a), AxialMm(b)), Edge = edge });
                }
            }
            foreach (object raw in (object[])Body.GetFaces()) Faces.Add((IFace2)raw);
        }

        private static double[] Point(IMathUtility math, IMathTransform t, double x, double y, double z)
        {
            IMathPoint p = (IMathPoint)math.CreatePoint(new double[] { x, y, z });
            return (double[])((IMathPoint)p.MultiplyTransform(t)).ArrayData;
        }
        private static double[] Unit(double[] v)
        {
            double n = Math.Sqrt(Dot(v, v)); DrawingHost.Need(n > 1e-12, "Mil ekseni belirlenemedi.");
            return new double[] { v[0]/n, v[1]/n, v[2]/n };
        }

        private const double Tol = 1e-3; // mm
        internal IEdge Circle(double x, double r)
        {
            foreach (AxialCircle c in Circles) if (Math.Abs(c.X-x) < Tol && Math.Abs(c.R-r) < Tol) return c.Edge;
            return null;
        }
        internal IEdge CircleIn(double x0, double x1, double r)
        {
            foreach (AxialCircle c in Circles) if (c.X > x0-Tol && c.X < x1+Tol && Math.Abs(c.R-r) < Tol) return c.Edge;
            return null;
        }
        internal IEdge PlaneAt(double x)
        {
            AxialCircle best = null;
            foreach (AxialCircle c in Circles) if (Math.Abs(c.X-x) < Tol && (best == null || c.R > best.R)) best = c;
            return best == null ? null : best.Edge;
        }
        internal IEdge Line(double y, double z, double x0, double x1)
        {
            foreach (AxisLine l in Lines)
                if (Math.Abs(l.Y-y) < Tol && Math.Abs(l.Z-z) < Tol && l.X0 > x0-Tol && l.X1 < x1+Tol) return l.Edge;
            return null;
        }
        internal IEdge Arc(double x, double y, double r)
        {
            foreach (FloorArc a in Arcs) if (Math.Abs(a.X-x) < Tol && Math.Abs(a.Y-y) < Tol && Math.Abs(a.R-r) < Tol) return a.Edge;
            return null;
        }
        internal IFace2 Cylinder(double x0, double x1, double r)
        {
            foreach (IFace2 face in Faces)
            {
                ISurface s = (ISurface)face.GetSurface();
                if (!s.IsCylinder()) continue;
                double[] p = (double[])s.CylinderParams; // origin(3), axis(3), radius
                if (Math.Abs(p[6]*1000 - r) > Tol || Math.Abs(Math.Abs(Dot(new double[] { p[3], p[4], p[5] }, Axis)) - 1) > 1e-6) continue;
                double[] box = (double[])face.GetBox();
                double a = AxialMm(new double[] { box[0], box[1], box[2] }), b = AxialMm(new double[] { box[3], box[4], box[5] });
                double lo = Math.Min(a, b), hi = Math.Max(a, b);
                if (hi > x0 + Tol && lo < x1 - Tol) return face;
            }
            return null;
        }
        internal IFace2 PlaneFace(double x, double rIn, double rOut)
        {
            foreach (IFace2 face in Faces)
            {
                ISurface s = (ISurface)face.GetSurface();
                if (!s.IsPlane()) continue;
                double[] p = (double[])s.PlaneParams; // normal(3), root(3)
                if (Math.Abs(Math.Abs(Dot(new double[] { p[0], p[1], p[2] }, Axis)) - 1) > 1e-6) continue;
                if (Math.Abs(AxialMm(new double[] { p[3], p[4], p[5] }) - x) < Tol) return face;
            }
            return null;
        }
        internal IFace2 FloorFace(double x0, double x1, double y)
        {
            foreach (IFace2 face in Faces)
            {
                ISurface s = (ISurface)face.GetSurface();
                if (!s.IsPlane()) continue;
                double[] p = (double[])s.PlaneParams;
                if (Math.Abs(Math.Abs(Dot(new double[] { p[0], p[1], p[2] }, Radial)) - 1) > 1e-6) continue;
                if (Math.Abs(RadialMm(new double[] { p[3], p[4], p[5] }) - y) < Tol) return face;
            }
            return null;
        }
    }

    public static class DrawingHost
    {
        [DllImport("oleaut32.dll", PreserveSig = false)]
        private static extern void GetActiveObject(ref Guid clsid, IntPtr reserved, [MarshalAs(UnmanagedType.IUnknown)] out object value);

        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 8000000, RecursionLimit = 64 };
        internal static IMathUtility MathUtility;
        private static ISldWorks app;
        private static string lastPhase = "Başlangıç";
        private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        // SOLIDWORKS (and OneDrive/antivirus on the Desktop) may keep a just-closed
        // file locked for a moment: "used by another process". Retry only sharing
        // violations, for at most ~10 s; never overwrite (File.Move refuses).
        internal static void MoveReleased(string source, string target)
        {
            for (int attempt = 0; ; attempt++)
            {
                try { File.Move(source, target); return; }
                catch (IOException error)
                {
                    if (File.Exists(target) || !File.Exists(source) || attempt >= 40 || (error.HResult & 0xFFFF) != 32 && (error.HResult & 0xFFFF) != 33) throw;
                    Thread.Sleep(250);
                }
                catch (UnauthorizedAccessException) { if (attempt >= 40) throw; Thread.Sleep(250); }
            }
        }
        internal static void DeleteReleased(string path)
        {
            for (int attempt = 0; File.Exists(path); attempt++)
            {
                try { File.Delete(path); return; }
                catch (IOException) { if (attempt >= 40) throw; Thread.Sleep(250); }
                catch (UnauthorizedAccessException) { if (attempt >= 40) throw; Thread.Sleep(250); }
            }
        }
        internal static void Need(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
        private static void Report(string phase)
        {
            lastPhase = phase;
            Console.WriteLine(Json.Serialize(new Dictionary<string, object> { { "event", "shaft_phase" }, { "phase", phase } }));
            Console.Out.Flush();
        }

        // ---- JSON helpers (plan is a nested dictionary) -------------------
        private static Dictionary<string, object> D(object o) { return (Dictionary<string, object>)o; }
        private static string S(Dictionary<string, object> d, string k) { object v; return d.TryGetValue(k, out v) && v != null ? Convert.ToString(v, Inv) : ""; }
        private static double N(Dictionary<string, object> d, string k) { return Convert.ToDouble(d[k], Inv); }
        private static bool B(Dictionary<string, object> d, string k) { object v; return d.TryGetValue(k, out v) && v is bool && (bool)v; }
        // JavaScriptSerializer.DeserializeObject returns JSON arrays as object[];
        // the drawing code reads them as ArrayList, so convert once, recursively.
        private static object Lists(object o)
        {
            var map = o as Dictionary<string, object>;
            if (map != null)
            {
                foreach (string key in new List<string>(map.Keys)) map[key] = Lists(map[key]);
                return map;
            }
            var array = o as object[];
            if (array != null)
            {
                var list = new ArrayList(array.Length);
                foreach (object item in array) list.Add(Lists(item));
                return list;
            }
            return o;
        }
        private static ArrayList L(Dictionary<string, object> d, string k) { object v; return d.TryGetValue(k, out v) && v is ArrayList ? (ArrayList)v : new ArrayList(); }
        private static string Mm(double v) { return v.ToString("0.####", Inv); }

        private static object ConnectRunningApplication(string progId)
        {
            Type server = Type.GetTypeFromProgID(progId, true); Guid clsid = server.GUID; object active;
            GetActiveObject(ref clsid, IntPtr.Zero, out active); return active;
        }

        private static string NewPath(Dictionary<string, object> r, string key, string extension, bool required)
        {
            string path = S(r, key);
            if (path.Length == 0) { Need(!required, key + " gerekli."); return ""; }
            Need(Path.IsPathRooted(path) && Path.GetExtension(path).Equals(extension, StringComparison.OrdinalIgnoreCase)
                && Directory.Exists(Path.GetDirectoryName(path)) && !File.Exists(path) && !Directory.Exists(path),
                "Yeni " + extension + " çıktı yolu gerekli; mevcut dosyanın üzerine yazılmaz: " + path);
            return path;
        }

        // Reads a request through the same parser and accessors as Run(), without
        // SOLIDWORKS. Used by the Windows CI test with the real JavaScriptSerializer.
        public static string CheckPayload(string line)
        {
            var request = D(Lists(Json.DeserializeObject(line)));
            var plan = D(request["plan"]); var layout = D(plan["layout"]); var sheet = D(layout["sheet"]);
            ArrayList scale = L(sheet, "scale");
            double s1 = Convert.ToDouble(scale[0], Inv), s2 = Convert.ToDouble(scale[1], Inv);
            double width = N(sheet, "width_mm"), height = N(sheet, "height_mm"); Paper(S(sheet, "size"));
            var viewBoxes = D(layout["views"]);
            foreach (string id in viewBoxes.Keys) BoxCentre(viewBoxes, id);
            foreach (object p in D(layout["placements"]).Values) { N(D(p), "x_mm"); N(D(p), "y_mm"); }
            int items = 0;
            foreach (string group in new string[] { "views", "dimensions", "notes", "finishes", "datums", "frames" })
                foreach (object raw in (ArrayList)plan[group]) { D(raw); items++; }
            foreach (object raw in L(plan, "segments")) { var seg = D(raw); N(seg, "x0"); N(seg, "x1"); N(seg, "r"); }
            foreach (object raw in (ArrayList)plan["dimensions"])
            {
                var dim = D(raw); N(dim, "nominal_mm");
                foreach (object r in (ArrayList)dim["refs"]) D(r);
                object t; if (dim.TryGetValue("tolerance", out t) && t != null)
                { var tol = D(t); Convert.ToInt32(tol["sw_type"], Inv); N(tol, "upper_mm"); N(tol, "lower_mm"); }
            }
            foreach (object raw in (ArrayList)plan["frames"])
            { var g = D(raw); N(g, "value"); foreach (object d in L(g, "datums")) Need(d is string, "datum harfi metin değil"); D(g["surface"]); }
            foreach (object raw in (ArrayList)plan["notes"]) D(D(raw)["ref"]);
            foreach (object raw in (ArrayList)plan["finishes"]) D(D(raw)["surface"]);
            D(plan["title"]);
            return Json.Serialize(new Dictionary<string, object> { { "scale", new double[] { s1, s2 } }, { "items", items },
                { "sheet", new double[] { width, height } }, { "process_id", Convert.ToInt32(request["process_id"], Inv) } });
        }

        public static void Run()
        {
            IModelDoc2 drawingModel = null; string previous = null; string temporary = null; string savedDrawing = "";
            var result = new Dictionary<string, object>();
            var issues = new List<string>();
            try
            {
                Need(Thread.CurrentThread.GetApartmentState() == ApartmentState.STA, "Drawing host must run in STA.");
                string line = Console.ReadLine(); if (line == null) return;
                var request = D(Lists(Json.DeserializeObject(line)));
                Need(S(request, "operation") == "create_shaft_drawing", "Desteklenmeyen teknik resim komutu.");
                var plan = D(request["plan"]);
                Need(B(plan, "ready"), "Teknik resim planında çözülmemiş hata var; çizim başlatılmadı.");
                string partPath = S(request, "part_path");
                Need(Path.IsPathRooted(partPath) && File.Exists(partPath) && Path.GetExtension(partPath).Equals(".sldprt", StringComparison.OrdinalIgnoreCase),
                    "Kayıtlı GOKWORKS mil parçası (.SLDPRT) bulunamadı: " + partPath);
                string drawingPath = NewPath(request, "drawing_path", ".slddrw", true);
                string pdfPath = NewPath(request, "pdf_path", ".pdf", false);
                string dwgPath = NewPath(request, "dwg_path", ".dwg", false);

                Report("Açık SOLIDWORKS oturumu doğrulanıyor");
                app = (ISldWorks)ConnectRunningApplication("SldWorks.Application");
                Need(app.GetProcessID() == Convert.ToInt32(request["process_id"], Inv), "SOLIDWORKS oturumu değişti; teknik resim oluşturulmadı.");
                MathUtility = (IMathUtility)app.GetMathUtility();
                IModelDoc2 active = (IModelDoc2)app.ActiveDoc; if (active != null) previous = active.GetTitle();

                Report("Mil parçası salt okunur açılıyor ve doğrulanıyor");
                IModelDoc2 part = (IModelDoc2)app.GetOpenDocumentByName(partPath);
                bool partWasOpen = part != null;
                if (part == null)
                {
                    int e = 0, w = 0;
                    part = (IModelDoc2)app.OpenDoc6(partPath, (int)swDocumentTypes_e.swDocPART,
                        (int)(swOpenDocOptions_e.swOpenDocOptions_Silent | swOpenDocOptions_e.swOpenDocOptions_ReadOnly), "", ref e, ref w);
                    Need(part != null && e == 0, "Parça açılamadı (" + e + "): " + partPath);
                }
                Need(part.GetType() == (int)swDocumentTypes_e.swDocPART, "Seçilen belge parça değil.");
                Need(!part.GetSaveFlag(), "Parçada kaydedilmemiş değişiklik var. Önce SOLIDWORKS'te kaydedin; teknik resim kayıtlı modele bağlanır.");
                Dictionary<string, double> drivingBefore = DrivingDimensions(part, plan);
                var shaft = new Shaft(part);

                Report("Teknik resim belgesi oluşturuluyor");
                var layout = D(plan["layout"]); var sheet = D(layout["sheet"]);
                string template = S(request, "template");
                if (template.Length == 0) template = app.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplateDrawing);
                Need(!String.IsNullOrWhiteSpace(template) && File.Exists(template),
                    "Teknik resim şablonu bulunamadı. Araçlar > Seçenekler > Varsayılan Şablonlar'da .drwdot seçin veya GOKWORKS'te şablon belirtin.");
                double width = N(sheet, "width_mm") * .001, height = N(sheet, "height_mm") * .001;
                int paper = Paper(S(sheet, "size"));
                drawingModel = (IModelDoc2)app.NewDocument(template, paper, width, height);
                Need(drawingModel != null && drawingModel.GetType() == (int)swDocumentTypes_e.swDocDRAWING && String.IsNullOrEmpty(drawingModel.GetPathName()),
                    "Yeni teknik resim belgesi oluşturulamadı.");
                IDrawingDoc drawing = (IDrawingDoc)drawingModel;
                ArrayList scale = L(sheet, "scale");
                double s1 = Convert.ToDouble(scale[0], Inv), s2 = Convert.ToDouble(scale[1], Inv);
                bool firstAngle = S(plan, "projection") != "third";
                SetupSheet(drawing, S(request, "sheet_format"), paper, s1, s2, firstAngle, width, height, issues);
                double factor = s1 / s2; PlannedFactor = factor;

                Report("Görünüşler oluşturuluyor");
                var views = new Dictionary<string, IView>();
                var viewBoxes = D(layout["views"]);
                IView main = MainView(drawing, part, partPath, shaft, BoxCentre(viewBoxes, "main"), factor, issues);
                if (B(D(((ArrayList)plan["views"])[0]), "hidden_lines"))
                    main.SetDisplayMode4(false, (int)swDisplayMode_e.swHIDDEN_GREYED, false, true, false);
                views["main"] = main;
                var viewResults = new List<object>();
                viewResults.Add(new Dictionary<string, object> { { "id", "main" }, { "name", main.GetName2() }, { "created", true } });
                foreach (object rawView in (ArrayList)plan["views"])
                {
                    var v = D(rawView); string id = S(v, "id"); string kind = S(v, "kind");
                    if (id == "main") continue;
                    IView created = null; string message = "";
                    try
                    {
                        double[] at = viewBoxes.ContainsKey(id) ? BoxCentre(viewBoxes, id) : new double[] { width * .8, height * .5 };
                        if (kind == "projected") created = Projected(drawing, main, at);
                        else if (kind == "section") created = Section(drawing, main, shaft, N(v, "x"), S(v, "label"), at);
                        else if (kind == "detail") created = Detail(drawing, main, shaft, v, factor, at);
                        else if (kind == "iso") created = ModelView(drawing, part, partPath, 7, at);
                        if (created == null) message = "SOLIDWORKS görünüşü oluşturmadı.";
                        else views[id] = created;
                    }
                    catch (Exception error) { message = error.Message; }
                    viewResults.Add(new Dictionary<string, object> { { "id", id }, { "name", created == null ? "" : created.GetName2() },
                                                                     { "created", created != null }, { "message", message } });
                    if (created == null) issues.Add("Görünüş oluşturulamadı: " + id + " · " + message);
                }
                result["views"] = viewResults;
                if (B(plan, "centerlines")) result["centerlines"] = Centerlines(drawingModel, drawing, views, shaft, plan, issues);

                Report("Ölçüler gerçek kenarlara bağlanıyor");
                var placements = D(layout["placements"]);
                var dimensionObjects = new Dictionary<string, IDisplayDimension>();
                var dimensionResults = new List<object>();
                foreach (object raw in (ArrayList)plan["dimensions"])
                {
                    var dim = D(raw);
                    dimensionResults.Add(Dimension(drawingModel, drawing, views, viewBoxes, placements, shaft, dim, dimensionObjects, issues));
                }
                result["dimensions"] = dimensionResults;

                Report("Notlar, yüzey işaretleri, datumlar ve geometrik toleranslar ekleniyor");
                var noteResults = new List<object>();
                foreach (object raw in (ArrayList)plan["notes"]) noteResults.Add(Note(drawingModel, drawing, views, viewBoxes, placements, shaft, D(raw), issues));
                result["notes"] = noteResults;
                var finishResults = new List<object>();
                foreach (object raw in (ArrayList)plan["finishes"]) finishResults.Add(Finish(drawingModel, drawing, views, viewBoxes, placements, shaft, D(raw), issues));
                result["finishes"] = finishResults;
                var datumResults = new List<object>();
                foreach (object raw in (ArrayList)plan["datums"]) datumResults.Add(Datum(drawingModel, drawing, views, viewBoxes, placements, shaft, D(raw), dimensionObjects, issues));
                result["datums"] = datumResults;
                var frameResults = new List<object>();
                foreach (object raw in (ArrayList)plan["frames"]) frameResults.Add(Frame(drawingModel, drawing, views, viewBoxes, placements, shaft, D(raw), issues));
                result["frames"] = frameResults;

                Report("Antet özellikleri yazılıyor");
                try { result["title"] = Title(drawingModel, part, D(plan["title"]), S(plan, "part_name"), issues); }
                catch (Exception error) { issues.Add("Antet özellikleri yazılamadı: " + error.Message); }
                // Diagnostic only: a missing annotation position must not cost the drawing.
                try { result["layout_conflicts"] = Overlaps(drawing, views); }
                catch (Exception error) { result["layout_conflicts"] = new List<object>(); issues.Add("Yerleşim çakışma kontrolü yapılamadı: " + error.Message); }

                Report("Teknik resim kaydediliyor, kapatılıp yeniden açılarak doğrulanıyor");
                // A dangling annotation can make the rebuild report failure; keep and save the
                // drawing, and say so, instead of discarding every created view.
                if (!drawingModel.ForceRebuild3(false)) issues.Add("Teknik resim rebuild uyarı verdi; kaydedilen resmi SOLIDWORKS'te kontrol edin.");
                temporary = Path.Combine(Path.GetDirectoryName(drawingPath), ".gokworks-" + Guid.NewGuid().ToString("N") + ".SLDDRW");
                int errors = 0, warnings = 0;
                Need(drawingModel.Extension.SaveAs3(temporary, 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref errors, ref warnings)
                     && errors == 0 && File.Exists(temporary), "SLDDRW kaydedilemedi: " + errors);
                string title = drawingModel.GetTitle(); drawingModel = null; drawing = null; views.Clear(); dimensionObjects.Clear();
                app.CloseDoc(title);
                if (app.GetOpenDocumentByName(temporary) != null) app.CloseDoc(temporary);
                Need(app.GetOpenDocumentByName(temporary) == null, "Geçici SLDDRW SOLIDWORKS'te kapatılamadı: " + temporary);
                MoveReleased(temporary, drawingPath); temporary = null; savedDrawing = drawingPath;
                drawingModel = (IModelDoc2)app.OpenDoc6(drawingPath, (int)swDocumentTypes_e.swDocDRAWING,
                    (int)swOpenDocOptions_e.swOpenDocOptions_Silent, "", ref errors, ref warnings);
                Need(drawingModel != null && errors == 0, "Kaydedilen teknik resim yeniden açılamadı: " + drawingPath);
                result["reopened"] = Verify(drawingModel, partPath, plan, issues);
                result["rebuild_success"] = drawingModel.ForceRebuild3(false);
                Dictionary<string, double> drivingAfter = DrivingDimensions(part, plan);
                bool unchanged = drivingBefore.Count == drivingAfter.Count;
                foreach (var pair in drivingBefore)
                    unchanged &= drivingAfter.ContainsKey(pair.Key) && Math.Abs(drivingAfter[pair.Key] - pair.Value) < 1e-12;
                result["part_unchanged"] = unchanged && !part.GetSaveFlag();
                if (!unchanged) issues.Add("Parçanın sürücü ölçüleri değişti; bu beklenmez. Parçayı kaydetmeden kapatın.");
                result["part_was_open"] = partWasOpen;

                if (pdfPath.Length > 0) { Report("PDF SOLIDWORKS teknik resminden üretiliyor"); result["pdf"] = Export(drawingModel, pdfPath, "%PDF", issues); }
                if (dwgPath.Length > 0) { Report("DWG dışa aktarılıyor"); result["dwg"] = Export(drawingModel, dwgPath, "AC10", issues); }

                result["success"] = true;
                result["process_id"] = Convert.ToInt32(request["process_id"], Inv);
                result["drawing_path"] = drawingPath;
                result["pdf_path"] = pdfPath; result["dwg_path"] = dwgPath;
                result["issues"] = issues;
                result["errors"] = new string[0];
                Console.WriteLine(Json.Serialize(result));
                drawingModel = null; // leave the verified drawing open for the user
            }
            catch (Exception error)
            {
                string cleanup = "";
                if (temporary != null)
                {
                    try { DeleteReleased(temporary); }
                    catch (Exception failure) { cleanup += " Geçici dosya silinemedi: " + failure.Message; }
                }
                if (drawingModel != null && savedDrawing.Length == 0)
                    cleanup += " Oluşturulan teknik resim inceleme için açık bırakıldı; kaydedilmedi.";
                if (drawingModel == null && app != null && previous != null)
                {
                    try { int code = 0; app.ActivateDoc3(previous, false, (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref code); } catch { }
                }
                result["success"] = false;
                result["drawing_path"] = savedDrawing;
                result["issues"] = issues;
                result["errors"] = new string[] { lastPhase + ": " + error.Message + cleanup };
                Console.WriteLine(Json.Serialize(result));
            }
            finally
            {
                if (app != null && Marshal.IsComObject(app)) Marshal.ReleaseComObject(app);
            }
        }

        // ---- part safety --------------------------------------------------
        private static Dictionary<string, double> DrivingDimensions(IModelDoc2 part, Dictionary<string, object> plan)
        {
            var values = new Dictionary<string, double>();
            int count = L(plan, "segments").Count;
            for (int i = 1; i < 200; i++)
            {
                string sketch = "MIL_PROFIL_" + i.ToString("00");
                IDimension diameter = (IDimension)part.Parameter("CAP_" + i.ToString("00") + "@" + sketch);
                IDimension length = (IDimension)part.Parameter("BOY_" + i.ToString("00") + "@" + sketch);
                if (diameter == null || length == null) break;
                values["CAP_" + i] = diameter.SystemValue; values["BOY_" + i] = length.SystemValue;
            }
            Need(values.Count >= 2 * Math.Max(1, count), "Parçada GOKWORKS kademe ölçüleri (CAP_nn/BOY_nn) bulunamadı.");
            return values;
        }

        // ---- sheet and views ----------------------------------------------
        private static int Paper(string size)
        {
            switch (size)
            {
                case "A4": return (int)swDwgPaperSizes_e.swDwgPaperA4size;
                case "A3": return (int)swDwgPaperSizes_e.swDwgPaperA3size;
                case "A2": return (int)swDwgPaperSizes_e.swDwgPaperA2size;
                case "A1": return (int)swDwgPaperSizes_e.swDwgPaperA1size;
                case "A0": return (int)swDwgPaperSizes_e.swDwgPaperA0size;
            }
            return (int)swDwgPaperSizes_e.swDwgPapersUserDefined;
        }

        private static void SetupSheet(IDrawingDoc drawing, string format, int paper, double s1, double s2, bool firstAngle,
                                       double width, double height, List<string> issues)
        {
            ISheet sheet = (ISheet)drawing.GetCurrentSheet();
            double[] props = (double[])sheet.GetProperties2(); // paper, template, scale1, scale2, firstAngle, width, height, same
            if (format.Length > 0)
            {
                Need(File.Exists(format), "Sayfa formatı bulunamadı: " + format);
                Need(drawing.SetupSheet5(sheet.GetName(), paper, (int)swDwgTemplates_e.swDwgTemplateCustom, s1, s2, firstAngle,
                    format, width, height, "Default", true), "Sayfa formatı uygulanamadı: " + format);
            }
            else
            {
                sheet.SetProperties2(paper, (int)props[1], s1, s2, firstAngle, width, height, true);
            }
            double[] check = (double[])((ISheet)drawing.GetCurrentSheet()).GetProperties2();
            Need(Math.Abs(check[2] - s1) < 1e-9 && Math.Abs(check[3] - s2) < 1e-9, "Sayfa ölçeği uygulanamadı.");
            if ((check[4] != 0) != firstAngle) issues.Add("Şablon izdüşüm yöntemini kabul etmedi; sayfa ayarlarını kontrol edin.");
        }

        private static double[] BoxCentre(Dictionary<string, object> views, string id)
        {
            ArrayList box = (ArrayList)D(views[id])["box"];
            return new double[] { (Convert.ToDouble(box[0], Inv) + Convert.ToDouble(box[2], Inv)) * .0005,
                                  (Convert.ToDouble(box[1], Inv) + Convert.ToDouble(box[3], Inv)) * .0005 };
        }

        private static double[] ToSheet(IView view, Shaft shaft, double x, double y, double z)
        {
            IMathPoint p = (IMathPoint)MathUtility.CreatePoint(shaft.ModelPoint(x, y, z));
            return (double[])((IMathPoint)p.MultiplyTransform(view.ModelToViewTransform)).ArrayData;
        }

        // swStandardViews_e order. A localized SOLIDWORKS names these views in its own
        // language (Turkish "*Ön", Chinese "*前视", PT-BR "*Frontal"), and
        // CreateDrawViewFromModelView3 silently returns null for the English name.
        // IModelDoc2.GetModelViewNames lists them in this fixed order (index ==
        // swStandardViews_e), so the name is read from the part itself.
        private static readonly string[] EnglishViews = { "*Normal To", "*Front", "*Back", "*Left", "*Right", "*Top", "*Bottom", "*Isometric" };

        internal static List<string> ViewNameCandidates(object modelViewNames, int standardView)
        {
            var candidates = new List<string>();
            object[] names = modelViewNames as object[];
            if (names != null && standardView < names.Length)
            {
                string local = names[standardView] as string;
                if (!String.IsNullOrEmpty(local) && local.StartsWith("*")) candidates.Add(local);
            }
            if (!candidates.Contains(EnglishViews[standardView])) candidates.Add(EnglishViews[standardView]);
            return candidates;
        }

        private static IView ModelView(IDrawingDoc drawing, IModelDoc2 part, string partPath, int standardView, double[] at)
        {
            object names = null;
            try { names = part.GetModelViewNames(); } catch (COMException) { }
            var tried = new List<string>();
            foreach (string name in ViewNameCandidates(names, standardView))
            {
                tried.Add(name);
                IView view = (IView)drawing.CreateDrawViewFromModelView3(partPath, name, at[0], at[1], 0);
                if (view != null) return view;
            }
            throw new InvalidOperationException("Model görünüşü oluşturulamadı (denenen adlar: " + String.Join(", ", tried) + ").");
        }

        private static IView MainView(IDrawingDoc drawing, IModelDoc2 part, string partPath, Shaft shaft, double[] at, double factor, List<string> issues)
        {
            // The viewer must look along +Normal so that +Axis is right and +Radial (keyway) is up.
            // Front, Back, Top, Bottom, Right, Left as swStandardViews_e values.
            int[] names = { 1, 2, 5, 6, 4, 3 };
            double[][] eyes = { new double[] { 0, 0, 1 }, new double[] { 0, 0, -1 }, new double[] { 0, 1, 0 },
                                new double[] { 0, -1, 0 }, new double[] { 1, 0, 0 }, new double[] { -1, 0, 0 } };
            int best = 0; double score = -2;
            for (int i = 0; i < names.Length; i++) { double d = Shaft.Dot(eyes[i], shaft.Normal); if (d > score) { score = d; best = i; } }
            Need(score > 1 - 1e-6, "Mil profil düzlemi standart model görünüşlerine dik değil; ana görünüş yönü belirlenemedi.");
            object modelViews = null;
            try { modelViews = part.GetModelViewNames(); } catch (COMException) { }
            // Expected name first; then every other standard ('*') view of the part, so a
            // version that orders or names them differently still yields the right view.
            var candidates = ViewNameCandidates(modelViews, names[best]);
            foreach (string other in Strings(modelViews)) if (other.StartsWith("*") && !candidates.Contains(other)) candidates.Add(other);
            IModelDoc2 model = (IModelDoc2)drawing;
            var tried = new List<string>();
            foreach (string name in candidates)
            {
                IView view = (IView)drawing.CreateDrawViewFromModelView3(partPath, name, at[0], at[1], 0);
                if (view == null) { tried.Add(name + " (oluşmadı)"); continue; }
                view.UseSheetScale = 1;
                // SOLIDWORKS may auto-scale a new view ('Auto-scale new drawing views'); the
                // layout was planned at the sheet scale, so enforce it and read it back.
                if (Math.Abs(view.ScaleDecimal - factor) > 1e-9 * Math.Max(1, factor))
                {
                    view.UseSheetScale = 0;
                    view.ScaleDecimal = factor;
                    if (Math.Abs(view.ScaleDecimal - factor) > 1e-9 * Math.Max(1, factor))
                        issues.Add("Ana görünüş ölçeği " + factor.ToString("0.####", Inv) + " yapılamadı (okunan "
                                   + view.ScaleDecimal.ToString("0.####", Inv) + "); ölçüler gerçek görünüşe göre yerleştirildi.");
                }
                if (Aligned(view, shaft))
                {
                    view.Position = at;
                    return view;
                }
                tried.Add(name + " (yön uymadı)");
                model.ClearSelection2(true);
                if (model.Extension.SelectByID2(view.GetName2(), "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0)) model.EditDelete();
                model.ClearSelection2(true);
            }
            throw new InvalidOperationException("Ana görünüş oluşturulamadı; mil ekseni yatay ve kama tarafı yukarı olan model görünüşü bulunamadı (denenen: "
                                                + String.Join(", ", tried) + ").");
        }

        // Judge the view from one reading of its transform (no reliance on SOLIDWORKS
        // refreshing ModelToViewTransform after Angle changes): it must look straight
        // along the profile normal and, once the shaft axis is turned horizontal, show
        // the keyway side up. Then rotate, and if the read-back shows the rotation went
        // the other way, use the opposite sign.
        private static bool Aligned(IView view, Shaft shaft)
        {
            double[] o = ToSheet(view, shaft, 0, 0, 0), a = ToSheet(view, shaft, 100, 0, 0);
            double[] r = ToSheet(view, shaft, 0, 100, 0), n = ToSheet(view, shaft, 0, 0, 100);
            double ax = a[0] - o[0], ay = a[1] - o[1], rx = r[0] - o[0], ry = r[1] - o[1];
            double length = Math.Sqrt(ax * ax + ay * ay);
            if (length < 1e-9) return false;
            double tolerance = length * 1e-6;
            if (Math.Abs(n[0] - o[0]) > tolerance || Math.Abs(n[1] - o[1]) > tolerance) return false;   // not straight-on
            double c = ax / length, s = ay / length;
            double radialUp = -rx * s + ry * c, radialAlong = rx * c + ry * s;   // radial after turning the axis to +x
            if (radialUp <= 0 || Math.Abs(radialAlong) > tolerance) return false;   // mirrored view (keyway would be down)
            double angle = Math.Atan2(ay, ax);
            if (Math.Abs(angle) < 1e-9) return true;
            double original = view.Angle;
            view.Angle = original - angle;
            double[] o2 = ToSheet(view, shaft, 0, 0, 0), a2 = ToSheet(view, shaft, 100, 0, 0);
            bool refreshed = Math.Abs((a2[0] - o2[0]) - ax) > tolerance || Math.Abs((a2[1] - o2[1]) - ay) > tolerance;
            if (refreshed && a2[0] - o2[0] < 0) view.Angle = original + angle;   // SOLIDWORKS turned the other way
            return true;
        }

        private static IView Projected(IDrawingDoc drawing, IView parent, double[] at)
        {
            IModelDoc2 model = (IModelDoc2)drawing; model.ClearSelection2(true);
            Need(drawing.ActivateView(parent.GetName2()), "Ana görünüş etkinleştirilemedi.");
            Need(model.Extension.SelectByID2(parent.GetName2(), "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0), "Ana görünüş seçilemedi.");
            return (IView)drawing.CreateUnfoldedViewAt3(at[0], at[1], 0, false);
        }

        private static IView Section(IDrawingDoc drawing, IView parent, Shaft shaft, double x, string label, double[] at)
        {
            IModelDoc2 model = (IModelDoc2)drawing; model.ClearSelection2(true);
            Need(drawing.ActivateView(parent.GetName2()), "Ana görünüş etkinleştirilemedi.");
            double reach = 0; foreach (AxialCircle c in shaft.Circles) reach = Math.Max(reach, c.R);
            double[] top = ToSheet(parent, shaft, x, reach + 6, 0), bottom = ToSheet(parent, shaft, x, -reach - 6, 0);
            model.SketchManager.AddToDB = true;
            ISketchSegment cut;
            try { cut = (ISketchSegment)model.SketchManager.CreateLine(top[0], top[1], 0, bottom[0], bottom[1], 0); }
            finally { model.SketchManager.AddToDB = false; }
            Need(cut != null && cut.Select4(false, null), "Kesit çizgisi oluşturulamadı.");
            return (IView)drawing.CreateSectionViewAt5(at[0], at[1], 0, label, 0, null, 0);
        }

        private static IView Detail(IDrawingDoc drawing, IView parent, Shaft shaft, Dictionary<string, object> v, double factor, double[] at)
        {
            IModelDoc2 model = (IModelDoc2)drawing; model.ClearSelection2(true);
            Need(drawing.ActivateView(parent.GetName2()), "Ana görünüş etkinleştirilemedi.");
            ArrayList centre = L(v, "center");
            double[] c = ToSheet(parent, shaft, Convert.ToDouble(centre[0], Inv), Convert.ToDouble(centre[1], Inv), 0);
            double radius = N(v, "radius") * .001 * factor;
            model.SketchManager.AddToDB = true;
            ISketchSegment circle;
            try { circle = (ISketchSegment)model.SketchManager.CreateCircleByRadius(c[0], c[1], 0, radius); }
            finally { model.SketchManager.AddToDB = false; }
            Need(circle != null && circle.Select4(false, null), "Detay dairesi oluşturulamadı.");
            double k = N(v, "enlargement");
            object view = drawing.CreateDetailViewAt4(at[0], at[1], 0, (int)swDetViewStyle_e.swDetViewSTANDARD, factor * k, 1,
                                                      S(v, "label"), (int)swDetCircleShowType_e.swDetCircleCIRCLE, true, false, false, 0);
            return view as IView;
        }

        private static List<object> Centerlines(IModelDoc2 model, IDrawingDoc drawing, Dictionary<string, IView> views, Shaft shaft,
                                                Dictionary<string, object> plan, List<string> issues)
        {
            var done = new List<object>();
            foreach (string id in new string[] { "main", "top" })
            {
                if (!views.ContainsKey(id)) continue;
                int count = 0;
                foreach (object raw in L(plan, "segments"))
                {
                    var seg = D(raw);
                    IFace2 face = shaft.Cylinder(N(seg, "x0"), N(seg, "x1"), N(seg, "r"));
                    if (face == null) continue;
                    model.ClearSelection2(true);
                    if (views[id].SelectEntity(face, false) && drawing.InsertCenterLine2() != null) count++;
                }
                done.Add(new Dictionary<string, object> { { "view", id }, { "count", count } });
                if (count == 0) issues.Add(id + " görünüşüne merkez çizgisi eklenemedi.");
            }
            model.ClearSelection2(true);
            return done;
        }

        // ---- references -----------------------------------------------------
        private static object Resolve(Shaft shaft, IView view, Dictionary<string, object> r)
        {
            string type = S(r, "type");
            if (type == "circle") return shaft.Circle(N(r, "x"), N(r, "r"));
            if (type == "circle_in") return shaft.CircleIn(N(r, "x0"), N(r, "x1"), N(r, "r"));
            if (type == "plane_x") return shaft.PlaneAt(N(r, "x"));
            if (type == "line") return shaft.Line(N(r, "y"), N(r, "z"), N(r, "x0"), N(r, "x1"));
            if (type == "arc") return shaft.Arc(N(r, "x"), N(r, "y"), N(r, "radius"));
            if (type == "silhouette")
            {
                object raw = view.GetVisibleEntities2(null, (int)swViewEntityType_e.swViewEntityType_SilhouetteEdge);
                if (raw == null) return null;
                foreach (object o in (object[])raw)
                {
                    ISilhouetteEdge edge = o as ISilhouetteEdge; if (edge == null) continue;
                    double[] a = Coordinates(edge.GetStartPoint()), b = Coordinates(edge.GetEndPoint());
                    double y = N(r, "y");
                    if (Math.Abs(shaft.RadialMm(a) - y) < 1e-3 && Math.Abs(shaft.RadialMm(b) - y) < 1e-3
                        && Math.Min(shaft.AxialMm(a), shaft.AxialMm(b)) < N(r, "x1") && Math.Max(shaft.AxialMm(a), shaft.AxialMm(b)) > N(r, "x0"))
                        return edge;
                }
                return null;
            }
            if (type == "cylinder") return shaft.Cylinder(N(r, "x0"), N(r, "x1"), N(r, "r"));
            if (type == "plane") return shaft.PlaneFace(N(r, "x"), N(r, "r_in"), N(r, "r_out"));
            if (type == "keyway_floor") return shaft.FloorFace(N(r, "x0"), N(r, "x1"), N(r, "y"));
            return null;
        }

        private static bool SelectIn(IView view, object entity, bool append)
        {
            if (entity == null) return false;
            ISilhouetteEdge silhouette = entity as ISilhouetteEdge;
            if (silhouette != null) return silhouette.Select2(append, null);
            return view.SelectEntity(entity, append);
        }

        internal static double PlannedFactor = 1;

        private static double[] Place(IView view, Shaft shaft, Dictionary<string, object> viewBoxes, Dictionary<string, object> placements,
                                      string viewId, string id, double fallbackX)
        {
            double[] outline = (double[])view.GetOutline();
            double cx = (outline[0] + outline[2]) / 2, cy = (outline[1] + outline[3]) / 2;
            if (!placements.ContainsKey(id) || !viewBoxes.ContainsKey(viewId))
                return new double[] { cx, outline[3] + .01 };
            var p = D(placements[id]);
            ArrayList box = (ArrayList)D(viewBoxes[viewId])["box"];
            double bx0 = Convert.ToDouble(box[0], Inv), by0 = Convert.ToDouble(box[1], Inv);
            double bx1 = Convert.ToDouble(box[2], Inv), by1 = Convert.ToDouble(box[3], Inv);
            double x = N(p, "x_mm"), y = N(p, "y_mm");
            if (viewId == "main" || viewId == "top")
            {
                // Along the axis: the planned paper position is a model position (planned
                // scale), mapped through the view's real ModelToViewTransform, so a view that
                // SOLIDWORKS scaled or moved still gets every dimension at its feature.
                // Across the axis: tiers keep their planned paper distance from the real
                // view outline.
                double[] axis = ToSheet(view, shaft, (x - bx0) / PlannedFactor, 0, 0);
                return AxisPlacement(axis, outline, S(p, "band"), by0, by1, y);
            }
            // Other views (sections, details): offset from the real outline centre.
            return new double[] { cx + (x - (bx0 + bx1) / 2) * .001, cy + (y - (by0 + by1) / 2) * .001 };
        }

        // Pure placement rule (no COM): axis = sheet point of the feature on the shaft axis;
        // outline = real view outline (sheet m); by0/by1/y = planned paper mm.
        public static double[] AxisPlacement(double[] axis, double[] outline, string band, double by0, double by1, double y)
        {
            double sheetY = band == "inside" ? axis[1]
                : band == "below" ? outline[1] - (by0 - y) * .001
                : band == "above" ? outline[3] + (y - by1) * .001
                : axis[1] + (y - (by0 + by1) / 2) * .001;
            return new double[] { axis[0], sheetY };
        }

        // Windows CI self-test of the SOLIDWORKS-free rules, with the real compiler/runtime.
        public static string SelfTest()
        {
            var failures = new List<string>();
            object[] turkish = { "*Normal", "*Ön", "*Arka", "*Sol", "*Sağ", "*Üst", "*Alt", "*İzometrik" };
            if (String.Join("|", ViewNameCandidates(turkish, 1)) != "*Ön|*Front") failures.Add("front:" + String.Join("|", ViewNameCandidates(turkish, 1)));
            if (String.Join("|", ViewNameCandidates(turkish, 7)) != "*İzometrik|*Isometric") failures.Add("iso");
            if (String.Join("|", ViewNameCandidates(new string[] { "*Front", "*Front" }, 1)) != "*Front") failures.Add("english");
            if (String.Join("|", ViewNameCandidates(null, 5)) != "*Top") failures.Add("none");
            double[] outline = { .05, .18, .25, .22 }, axis = { .1, .2 };
            double[] below = AxisPlacement(axis, outline, "below", 100, 150, 90);
            double[] above = AxisPlacement(axis, outline, "above", 100, 150, 158);
            double[] inside = AxisPlacement(axis, outline, "inside", 100, 150, 125);
            if (Math.Abs(below[0] - .1) > 1e-12 || Math.Abs(below[1] - .17) > 1e-12) failures.Add("below");
            if (Math.Abs(above[1] - .228) > 1e-12) failures.Add("above");
            if (Math.Abs(inside[1] - .2) > 1e-12) failures.Add("inside");
            return Json.Serialize(new Dictionary<string, object> { { "self_test", failures.Count == 0 }, { "failures", failures } });
        }

        // COM arrays arrive as string[], object[] or double[] depending on the call.
        private static string[] Strings(object raw)
        {
            var array = raw as Array; if (array == null) return new string[0];
            var values = new string[array.Length];
            for (int i = 0; i < array.Length; i++) values[i] = Convert.ToString(array.GetValue(i), Inv) ?? "";
            return values;
        }
        private static double[] Coordinates(object raw)
        {
            IMathPoint point = raw as IMathPoint; if (point != null) raw = point.ArrayData;
            var array = raw as Array; Need(array != null && array.Length >= 3, "nokta okunamadı");
            return new double[] { Convert.ToDouble(array.GetValue(0), Inv), Convert.ToDouble(array.GetValue(1), Inv), Convert.ToDouble(array.GetValue(2), Inv) };
        }

        private static bool Close(double a, double b) { return Math.Abs(a - b) < 1e-7; }

        // ---- dimensions -------------------------------------------------------
        private static Dictionary<string, object> Dimension(IModelDoc2 model, IDrawingDoc drawing, Dictionary<string, IView> views,
            Dictionary<string, object> viewBoxes, Dictionary<string, object> placements, Shaft shaft, Dictionary<string, object> dim,
            Dictionary<string, IDisplayDimension> created, List<string> issues)
        {
            string id = S(dim, "id"), viewId = S(dim, "view"), label = S(dim, "label");
            var row = new Dictionary<string, object> { { "id", id }, { "target", S(dim, "target") }, { "created", false } };
            try
            {
                Need(views.ContainsKey(viewId), "görünüş yok: " + viewId);
                IView view = views[viewId];
                Need(drawing.ActivateView(view.GetName2()), "görünüş etkinleştirilemedi");
                model.ClearSelection2(true);
                ArrayList refs = (ArrayList)dim["refs"];
                var entities = new List<object>();
                foreach (object r in refs)
                {
                    object entity = Resolve(shaft, view, D(r));
                    Need(entity != null, "model kenarı bulunamadı (" + S(D(r), "type") + ")");
                    entities.Add(entity);
                }
                for (int i = 0; i < entities.Count; i++)
                    Need(SelectIn(view, entities[i], i > 0), "kenar görünüşte seçilemedi");
                double[] at = Place(view, shaft, viewBoxes, placements, viewId, id, 0);
                if (S(dim, "kind") == "diameter" && (viewId == "main" || viewId == "top"))
                {
                    // Diameter text in the upper half of the step, clear of the centre line.
                    double xm = (N(dim, "x0_mm") + N(dim, "x1_mm")) / 2;
                    double[] text = ToSheet(view, shaft, xm, N(dim, "nominal_mm") / 4, 0);
                    at = new double[] { text[0], text[1] };
                }
                IDisplayDimension display = (IDisplayDimension)model.AddDimension2(at[0], at[1], 0);
                Need(display != null, "SOLIDWORKS ölçü oluşturmadı");
                IDimension dimension = display.GetDimension2(0);
                string kind = S(dim, "kind");
                if (kind == "keyway_length" || kind == "keyway_position")
                {
                    for (int i = 0; i < refs.Count; i++)
                    {
                        string condition = S(D(refs[i]), "condition");
                        if (condition.Length == 0) continue;
                        dimension.SetArcEndCondition(i + 1, condition == "max" ? (int)swArcEndCondition_e.swArcEndConditionMax
                                                                                 : (int)swArcEndCondition_e.swArcEndConditionMin);
                    }
                    model.ForceRebuild3(false);
                }
                double expected = N(dim, "nominal_mm") * .001;
                double value = dimension.SystemValue;
                row["value_mm"] = value * 1000;
                if (!Close(value, expected))
                {
                    ((IAnnotation)display.GetAnnotation()).Select3(false, null); model.EditDelete();
                    throw new InvalidOperationException("ölçü değeri " + Mm(value * 1000) + " mm, beklenen " + Mm(expected * 1000) + " mm; silindi");
                }
                // 40 not "40,00": whole millimetres without decimals, otherwise only the
                // decimals the value needs (tolerance digits follow the document).
                double nominal = N(dim, "nominal_mm"); int decimals = 0;
                while (decimals < 3 && Math.Abs(nominal * Math.Pow(10, decimals) - Math.Round(nominal * Math.Pow(10, decimals))) > 1e-6) decimals++;
                // Tolerance digits are set explicitly: following a 0-decimal nominal they
                // showed "js6 0 0" for ±0,0065.
                int tolDecimals = -1;
                object tolRaw; dim.TryGetValue("tolerance", out tolRaw);
                if (tolRaw != null)
                {
                    var tolSpec = D(tolRaw); tolDecimals = 2;
                    foreach (double v in new double[] { N(tolSpec, "upper_mm"), N(tolSpec, "lower_mm") })
                        while (tolDecimals < 4 && Math.Abs(v * Math.Pow(10, tolDecimals) - Math.Round(v * Math.Pow(10, tolDecimals))) > 1e-6) tolDecimals++;
                }
                display.SetPrecision3(decimals, -1, tolDecimals, -1);
                if (S(dim, "prefix") == "Ø" && display.GetType() != (int)swDimensionType_e.swDiameterDimension)
                    display.SetText((int)swDimensionTextParts_e.swDimensionTextPrefix, "<MOD-DIAM>");
                if (B(dim, "reference")) display.ShowParenthesis = true;
                object tolerance; dim.TryGetValue("tolerance", out tolerance);
                if (tolerance != null) row["tolerance_ok"] = Tolerance(dimension, D(tolerance), S(dim, "prefix") == "Ø" && S(dim, "target") == "bore:diameter");
                row["created"] = true; created[id] = display;
                if (row.ContainsKey("tolerance_ok") && !(bool)row["tolerance_ok"]) issues.Add(label + ": tolerans geri okunamadı veya farklı.");
            }
            catch (Exception error)
            {
                row["message"] = error.Message;
                issues.Add(label + ": " + error.Message);
            }
            model.ClearSelection2(true);
            return row;
        }

        private static bool Tolerance(IDimension dimension, Dictionary<string, object> t, bool hole)
        {
            IDimensionTolerance tolerance = dimension.Tolerance;
            int type = Convert.ToInt32(t["sw_type"], Inv);
            double upper = N(t, "upper_mm") * .001, lower = N(t, "lower_mm") * .001;
            tolerance.Type = type;
            if (type == (int)swTolType_e.swTolFIT || type == (int)swTolType_e.swTolFITWITHTOL || type == (int)swTolType_e.swTolFITTOLONLY)
            {
                string fit = S(t, "fit");
                if (!tolerance.SetFitValues(hole ? fit : "", hole ? "" : fit)) return false;
            }
            else if (type == (int)swTolType_e.swTolSYMMETRIC)
            {
                if (!tolerance.SetValues2(-upper, upper, (int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration, null)) return false;
            }
            else if (!tolerance.SetValues2(lower, upper, (int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration, null)) return false;
            if (tolerance.Type != type) return false;
            // SOLIDWORKS computes fit deviations from its own tables: they must agree
            // with the verified ISO 286 data used by GOKWORKS.
            return Close(tolerance.GetMaxValue(), upper) && Close(tolerance.GetMinValue(), lower);
        }

        // ---- annotations ------------------------------------------------------
        private static Dictionary<string, object> Note(IModelDoc2 model, IDrawingDoc drawing, Dictionary<string, IView> views,
            Dictionary<string, object> viewBoxes, Dictionary<string, object> placements, Shaft shaft, Dictionary<string, object> n, List<string> issues)
        {
            var row = new Dictionary<string, object> { { "id", S(n, "id") }, { "created", false } };
            try
            {
                IView view = views[S(n, "view")];
                Need(drawing.ActivateView(view.GetName2()), "görünüş etkinleştirilemedi");
                model.ClearSelection2(true);
                var reference = D(n["ref"]);
                object entity = Resolve(shaft, view, reference);
                Need(entity != null, "not hedef kenarı bulunamadı");
                // Pick the edge at its upper end, so the leader starts there and stays short
                // instead of crossing the shaft from an arbitrary point of the edge.
                bool picked = false;
                if (reference.ContainsKey("x") && reference.ContainsKey("r"))
                {
                    double[] pick = ToSheet(view, shaft, N(reference, "x"), N(reference, "r") * .85, 0);
                    picked = model.Extension.SelectByID2("", "EDGE", pick[0], pick[1], 0, false, 0, null, 0);
                }
                if (!picked) Need(SelectIn(view, entity, false), "not hedef kenarı seçilemedi");
                INote note = (INote)model.InsertNote(S(n, "text"));
                Need(note != null, "SOLIDWORKS notu oluşturmadı");
                double[] at = Place(view, shaft, viewBoxes, placements, S(n, "view"), S(n, "id"), 0);
                ((IAnnotation)note.GetAnnotation()).SetPosition2(at[0], at[1], 0);
                Need(note.GetText() == S(n, "text"), "not metni geri okunamadı");
                Need(Attached((IAnnotation)note.GetAnnotation(), entity), "not hedef kenara bağlanmadı");
                row["created"] = true;
            }
            catch (Exception error) { row["message"] = error.Message; issues.Add(S(n, "text") + ": " + error.Message); }
            model.ClearSelection2(true);
            return row;
        }

        private static bool Attached(IAnnotation annotation, object entity)
        {
            // A drawing annotation reports the drawing-side entity (view edge/face), which is
            // never IsSame with the model entity selected through IView.SelectEntity; any
            // attachment after that selection is the requested one.
            object raw = annotation.GetAttachedEntities3();
            object[] attached = raw as object[];
            return attached != null && attached.Length > 0;
        }

        private static Dictionary<string, object> Finish(IModelDoc2 model, IDrawingDoc drawing, Dictionary<string, IView> views,
            Dictionary<string, object> viewBoxes, Dictionary<string, object> placements, Shaft shaft, Dictionary<string, object> f, List<string> issues)
        {
            var row = new Dictionary<string, object> { { "id", S(f, "id") }, { "target", S(f, "target") }, { "created", false } };
            try
            {
                IView view = views[S(f, "view")];
                Need(drawing.ActivateView(view.GetName2()), "görünüş etkinleştirilemedi");
                model.ClearSelection2(true);
                object face = Resolve(shaft, view, D(f["surface"]));
                Need(face != null, "hedef yüzey modelde bulunamadı");
                Need(view.SelectEntity(face, false), "hedef yüzey görünüşte seçilemedi");
                string process = S(f, "process");
                int symbol = process == "removal_required" ? (int)swSFSymType_e.swSFMachining_Req
                           : process == "removal_prohibited" ? (int)swSFSymType_e.swSFDont_Machine : (int)swSFSymType_e.swSFBasic;
                double[] at = Place(view, shaft, viewBoxes, placements, S(f, "view"), S(f, "id"), 0);
                var surface = D(f["surface"]); int leader = (int)swLeaderStyle_e.swSTRAIGHT;
                if (S(surface, "type") == "cylinder" && (S(f, "view") == "main" || S(f, "view") == "top"))
                {
                    // ISO 1302: the symbol stands on the surface line itself; no leader across the view.
                    at = ToSheet(view, shaft, (N(surface, "x0") + N(surface, "x1")) / 2, N(surface, "r"), 0);
                    leader = (int)swLeaderStyle_e.swNO_LEADER;
                }
                string text = S(f, "text");
                ISFSymbol sf = (ISFSymbol)model.Extension.InsertSurfaceFinishSymbol3(symbol, leader, at[0], at[1], 0,
                    Lay(S(f, "lay")), (int)swArrowStyle_e.swCLOSED_ARROWHEAD, "", "", S(f, "method"), "", text, "", "");
                Need(sf != null, "SOLIDWORKS yüzey işaretini oluşturmadı");
                Need(sf.GetSymbol() == symbol, "yüzey işareti türü geri okunamadı");
                Need(sf.GetText((int)swSurfaceFinishSymbolText_e.swSFSymbolMaximumRoughness).Trim() == text, "Ra değeri geri okunamadı");
                Need(Attached((IAnnotation)sf.GetAnnotation(), face), "işaret hedef yüzeye bağlanmadı");
                row["created"] = true;
            }
            catch (Exception error) { row["message"] = error.Message; issues.Add(S(f, "title") + " " + S(f, "text") + ": " + error.Message); }
            model.ClearSelection2(true);
            return row;
        }

        private static int Lay(string lay)
        {
            switch (lay)
            {
                case "=": return (int)swSFLaySym_e.swSFParallel;
                case "⊥": return (int)swSFLaySym_e.swSFPerp;
                case "X": return (int)swSFLaySym_e.swSFCross;
                case "M": return (int)swSFLaySym_e.swSFMultiDir;
                case "C": return (int)swSFLaySym_e.swSFCircular;
                case "R": return (int)swSFLaySym_e.swSFRadial;
                case "P": return (int)swSFLaySym_e.swSFParticulate;
            }
            return (int)swSFLaySym_e.swSFNone;
        }

        private static Dictionary<string, object> Datum(IModelDoc2 model, IDrawingDoc drawing, Dictionary<string, IView> views,
            Dictionary<string, object> viewBoxes, Dictionary<string, object> placements, Shaft shaft, Dictionary<string, object> d,
            Dictionary<string, IDisplayDimension> dimensions, List<string> issues)
        {
            var row = new Dictionary<string, object> { { "id", S(d, "id") }, { "created", false } };
            try
            {
                IView view = views[S(d, "view")];
                Need(drawing.ActivateView(view.GetName2()), "görünüş etkinleştirilemedi");
                model.ClearSelection2(true);
                string attach = S(d, "attach");
                object target;
                if (attach == "surface")
                {
                    target = Resolve(shaft, view, D(d["surface"]));
                    Need(view.SelectEntity(target, false), "datum yüzeyi seçilemedi");
                }
                else
                {
                    Need(dimensions.ContainsKey(attach), "eksen datumu için çap ölçüsü oluşturulmamış");
                    IAnnotation annotation = (IAnnotation)dimensions[attach].GetAnnotation();
                    Need(annotation.Select3(false, null), "çap ölçüsü seçilemedi");
                    target = annotation;
                }
                IDatumTag tag = (IDatumTag)model.InsertDatumTag2();
                Need(tag != null, "SOLIDWORKS datum etiketi oluşturmadı");
                Need(tag.SetLabel(S(d, "label")) && tag.GetLabel() == S(d, "label"), "datum harfi geri okunamadı");
                double[] at = Place(view, shaft, viewBoxes, placements, S(d, "view"), S(d, "id"), 0);
                ((IAnnotation)tag.GetAnnotation()).SetPosition2(at[0], at[1], 0);
                row["created"] = true;
            }
            catch (Exception error) { row["message"] = error.Message; issues.Add("Datum " + S(d, "label") + ": " + error.Message); }
            model.ClearSelection2(true);
            return row;
        }

        private static readonly Dictionary<string, string> GtolSymbols = new Dictionary<string, string> {
            { "circular_runout", "<IGTOL-SRUN>" }, { "total_runout", "<IGTOL-TRUN>" }, { "cylindricity", "<IGTOL-CYL>" },
            { "perpendicularity", "<IGTOL-PERP>" }, { "parallelism", "<IGTOL-PARA>" }, { "position", "<IGTOL-POSI>" } };

        private static Dictionary<string, object> Frame(IModelDoc2 model, IDrawingDoc drawing, Dictionary<string, IView> views,
            Dictionary<string, object> viewBoxes, Dictionary<string, object> placements, Shaft shaft, Dictionary<string, object> g, List<string> issues)
        {
            var row = new Dictionary<string, object> { { "id", S(g, "id") }, { "created", false } };
            try
            {
                IView view = views[S(g, "view")];
                Need(drawing.ActivateView(view.GetName2()), "görünüş etkinleştirilemedi");
                model.ClearSelection2(true);
                object face = Resolve(shaft, view, D(g["surface"]));
                Need(face != null && view.SelectEntity(face, false), "hedef yüzey seçilemedi");
                IGtol gtol = (IGtol)model.InsertGtol();
                Need(gtol != null, "SOLIDWORKS geometrik tolerans çerçevesi oluşturmadı");
                ArrayList datums = L(g, "datums");
                string d1 = datums.Count > 0 ? (string)datums[0] : "", d2 = datums.Count > 1 ? (string)datums[1] : "", d3 = datums.Count > 2 ? (string)datums[2] : "";
                gtol.SetFrameSymbols2(1, GtolSymbols[S(g, "characteristic")], B(g, "diameter_zone"), "", false, "", "", "", "");
                string value = N(g, "value").ToString("0.###", CultureInfo.GetCultureInfo("tr-TR"));
                Need(gtol.SetFrameValues2(1, value, "", d1, d2, d3), "çerçeve değerleri yazılamadı");
                string[] back = Strings(gtol.GetFrameValues(1));
                Need(back.Length >= 3 && back[0].Trim() == value && back[2].Trim() == d1, "çerçeve değerleri geri okunamadı");
                double[] at = Place(view, shaft, viewBoxes, placements, S(g, "view"), S(g, "id"), 0);
                ((IAnnotation)gtol.GetAnnotation()).SetPosition2(at[0], at[1], 0);
                Need(Attached((IAnnotation)gtol.GetAnnotation(), face), "çerçeve hedef yüzeye bağlanmadı");
                row["created"] = true;
            }
            catch (Exception error) { row["message"] = error.Message; issues.Add(S(g, "text") + ": " + error.Message); }
            model.ClearSelection2(true);
            return row;
        }

        // ---- title block, verification, export -------------------------------
        private static Dictionary<string, object> Title(IModelDoc2 drawing, IModelDoc2 part, Dictionary<string, object> title, string partName, List<string> issues)
        {
            var written = new Dictionary<string, object>();
            ICustomPropertyManager props = drawing.Extension.get_CustomPropertyManager("");
            string material = S(title, "material");
            if (material.Length == 0)
            {
                string database;
                material = ((IPartDoc)part).GetMaterialPropertyName2("", out database) ?? "";
                if (material.Length == 0) issues.Add("Malzeme tanımlı değil; antete malzeme yazılmadı.");
            }
            var fields = new Dictionary<string, string> {
                { "GOKWORKS_PARCA", partName }, { "Malzeme", material }, { "ResimNo", S(title, "drawing_number") },
                { "Revizyon", S(title, "revision") }, { "GenelTolerans", S(title, "general_tolerance") },
                { "Cizen", S(title, "drawn_by") }, { "Aciklama", S(title, "notes") },
                { "Tarih", DateTime.Now.ToString("dd.MM.yyyy", Inv) } };
            foreach (var pair in fields)
            {
                if (pair.Value.Length == 0) continue;
                int status = props.Add3(pair.Key, (int)swCustomInfoType_e.swCustomInfoText, pair.Value,
                                        (int)swCustomPropertyAddOption_e.swCustomPropertyReplaceValue);
                written[pair.Key] = status == (int)swCustomInfoAddResult_e.swCustomInfoAddResult_AddedOrChanged;
            }
            return written;
        }

        private static List<object> Overlaps(IDrawingDoc drawing, Dictionary<string, IView> views)
        {
            // Read back every annotation position and report overlapping text anchors
            // (approximate boxes: 3.5 mm text, 2.2 mm per character).
            var boxes = new List<KeyValuePair<string, double[]>>();
            foreach (var pair in views)
            {
                for (IDisplayDimension d = pair.Value.GetFirstDisplayDimension5(); d != null; d = d.GetNext5())
                {
                    IAnnotation a = (IAnnotation)d.GetAnnotation();
                    double[] p = (double[])a.GetPosition();
                    string text = d.GetText((int)swDimensionTextParts_e.swDimensionTextAll) ?? "";
                    double w = Math.Max(.006, (text.Length + 4) * .0022), h = .0035;
                    boxes.Add(new KeyValuePair<string, double[]>(pair.Key + ":" + a.GetName(), new double[] { p[0] - w / 2, p[1] - h / 2, p[0] + w / 2, p[1] + h / 2 }));
                }
            }
            var conflicts = new List<object>();
            for (int i = 0; i < boxes.Count; i++)
                for (int j = i + 1; j < boxes.Count; j++)
                {
                    double[] a = boxes[i].Value, b = boxes[j].Value;
                    if (a[2] > b[0] && b[2] > a[0] && a[3] > b[1] && b[3] > a[1]) conflicts.Add(boxes[i].Key + " ↔ " + boxes[j].Key);
                }
            return conflicts;
        }

        private static Dictionary<string, object> Verify(IModelDoc2 model, string partPath, Dictionary<string, object> plan, List<string> issues)
        {
            IDrawingDoc drawing = (IDrawingDoc)model;
            int views = 0, dimensions = 0, symbols = 0, datums = 0, frames = 0; bool references = true;
            object[] sheetViews = (object[])drawing.GetViews();
            foreach (object rawSheet in sheetViews)
            {
                object[] list = (object[])rawSheet;
                for (int i = 1; i < list.Length; i++) // index 0 is the sheet itself
                {
                    IView view = (IView)list[i]; views++;
                    references &= String.Equals(Path.GetFullPath(view.GetReferencedModelName()), Path.GetFullPath(partPath), StringComparison.OrdinalIgnoreCase);
                    for (IDisplayDimension d = view.GetFirstDisplayDimension5(); d != null; d = d.GetNext5()) dimensions++;
                    object sf = view.GetSFSymbols(); if (sf != null) symbols += ((object[])sf).Length;
                    object tags = view.GetDatumTags(); if (tags != null) datums += ((object[])tags).Length;
                    object gtols = view.GetGTols(); if (gtols != null) frames += ((object[])gtols).Length;
                }
            }
            if (!references) issues.Add("Bir veya daha fazla görünüş beklenen SLDPRT dosyasına bağlı değil.");
            return new Dictionary<string, object> { { "views", views }, { "dimensions", dimensions }, { "surface_symbols", symbols },
                { "datums", datums }, { "frames", frames }, { "references_ok", references } };
        }

        private static Dictionary<string, object> Export(IModelDoc2 model, string path, string magic, List<string> issues)
        {
            string temporary = Path.Combine(Path.GetDirectoryName(path), ".gokworks-" + Guid.NewGuid().ToString("N") + Path.GetExtension(path));
            int errors = 0, warnings = 0; bool ok = false;
            try
            {
                ok = model.Extension.SaveAs3(temporary, 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref errors, ref warnings)
                     && errors == 0 && File.Exists(temporary) && new FileInfo(temporary).Length > 512;
                if (ok)
                {
                    byte[] head = new byte[4];
                    using (FileStream s = File.OpenRead(temporary)) s.Read(head, 0, 4);
                    ok = System.Text.Encoding.ASCII.GetString(head).StartsWith(magic.Substring(0, Math.Min(magic.Length, 4)));
                }
                if (ok) MoveReleased(temporary, path);
            }
            finally { try { DeleteReleased(temporary); } catch (IOException) { } catch (UnauthorizedAccessException) { } }
            if (!ok) issues.Add(Path.GetExtension(path).ToUpperInvariant() + " dışa aktarımı doğrulanamadı (" + errors + ").");
            return new Dictionary<string, object> { { "path", ok ? path : "" }, { "verified", ok } };
        }
    }
}
