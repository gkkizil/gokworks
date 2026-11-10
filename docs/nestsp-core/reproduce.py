import json,time,sys
from pathlib import Path
from shapely import affinity
from shapely.geometry import Polygon,Point,box
from modules.nesting.materials import new_project
from modules.nesting.models import Part,Sheet
from modules.nesting.solver import nest
from modules.nesting.layout_score import layout_score
from modules.nesting.storage import save_project
from modules.nesting.geometry import placed
from modules.nesting.validation import validate_result
p=new_project();p.name="Original twelve perforated profiles";p.sheets=[Sheet("sheet","1250 x 2500",1250,2500,8)]
shapes=[]
for i in range(4):
 g=Polygon([(0,30),(30,0),(390,0),(420,30),(420,60),(390,80),(30,80),(0,60)])
 for x in (45,210,375):g=g.difference(Point(x,40).buffer(5.5,quad_segs=8))
 shapes.append(affinity.rotate(g,45 if i%2==0 else -45,origin=(0,0)))
for i in range(4):
 g=Polygon([(0,20),(20,0),(228,0),(248,20),(248,60),(228,80),(20,80),(0,60)])
 shapes.append(affinity.rotate(g,90*(i%2),origin=(0,0)))
for i in range(4):
 g=Polygon([(0,25),(25,0),(137.5,0),(162.5,25),(162.5,137.5),(137.5,162.5),(25,162.5),(0,137.5)])
 for x,y in ((40,40),(120,40),(80,110)):g=g.difference(Point(x,y).buffer(5.5,quad_segs=8))
 shapes.append(g)
p.parts=[Part("p"+str(i),"Profile "+str(i),__import__("shapely").geometry.mapping(g),"S235JR",8) for i,g in enumerate(shapes)]
p.options.quality="Yüksek";p.options.seconds=8
if len(sys.argv)>2 and sys.argv[2]=="free":p.options.angles=None
start=time.monotonic();r=nest(p);validate_result(p,r)
boxes=[placed(p.part(row.part_id),row).bounds for row in r.placements]
report=dict(elapsed=time.monotonic()-start,score=layout_score(p,r),iterations=r.iterations,placements=len(r.placements),bbox_area=(max(b[2] for b in boxes)-min(b[0] for b in boxes))*(max(b[3] for b in boxes)-min(b[1] for b in boxes)),angles=sorted(set(round(row.angle,3) for row in r.placements)),engine=r.engine_version)
print(json.dumps(report,ensure_ascii=False),flush=True)
Path(sys.argv[1]+".json").write_text(json.dumps(report,ensure_ascii=False,indent=2));save_project(p,sys.argv[1]+".goknest.json",r,overwrite=True)
