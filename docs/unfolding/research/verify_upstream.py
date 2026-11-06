"""Reproduce bounded numerical comparisons against the pinned research checkouts.

Run with Python 3.13 and Node 24; neither FreeCAD nor npm installation is needed.
The FreeCAD probe executes only the extracted scalar lookup method, not its CAD
runtime. This does not establish that an entire upstream application works.
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
from types import SimpleNamespace

from core.unfolding.bend_profiles import BendInput, calibrate_k, develop_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(Path(__file__).with_name('references.json').read_text())['repositories']
    for record in records:
        folder = args.research_root/record['checkout_name']
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=folder, text=True).strip()
        if actual != record['commit']:
            raise ValueError(f'{folder.name}: research commit changed')
        for reviewed in record['reviewed_files']:
            if hashlib.sha256((folder/reviewed['path']).read_bytes()).hexdigest() != reviewed['sha256']:
                raise ValueError(f"{folder.name}/{reviewed['path']}: reviewed source changed")
    report = {'scope': 'isolated numerical probes, not upstream GUI/CAD acceptance',
              'repositories': len(records), 'runtime': {'node': subprocess.check_output(['node', '--version'], text=True).strip()}}
    rng = random.Random(20261106)
    cases = []
    for _ in range(128):
        count = rng.randint(2, 6)
        cases.append(dict(thickness=rng.uniform(.5, 6), radius=rng.uniform(.5, 12),
            k=rng.uniform(.15, .6), dimType=rng.choice(('inside', 'outside', 'flat')),
            lengths=[rng.uniform(500, 1000) for _ in range(count)],
            bends=[dict(angle=rng.uniform(5, 150), dir=rng.choice((-1, 1))) for _ in range(count-1)]))
    # The reviewed upstream module is pure scalar TypeScript; Node strips types.
    upstream = args.research_root/'sheet-metal-unfold/src/lib/bend.ts'
    js = """
      const {computeFlat,kFromTestBend}=await import(process.argv[1]);
      let text=''; for await (const chunk of process.stdin) text+=chunk;
      console.log(JSON.stringify(JSON.parse(text).map(p=>{
        const r=computeFlat(p); return {r,k:kFromTestBend(40,60,96.67842872136355,90,3,1.5)};
      })));
    """
    output = subprocess.check_output(['node', '--disable-warning=ExperimentalWarning', '--input-type=module', '-e', js,
                                      upstream.resolve().as_uri()], input=json.dumps(cases), text=True)
    reference = json.loads(output)
    errors = []
    for p, upstream_result in zip(cases, reference, strict=True):
        r = develop_profile(p['lengths'], tuple(BendInput(v['angle']*v['dir'], p['radius'], p['k'])
                            for v in p['bends']), p['thickness'],
                            dimension_reference='tangent' if p['dimType']=='flat' else p['dimType'])
        other = upstream_result['r']
        errors += [abs(r.flat_length_mm-other['flatLength'])]
        errors += [abs(v.line_at_mm-w['lineAt']) for v, w in zip(r.bends, other['bends'], strict=True)]
    assert max(errors) < 1e-9
    assert abs(calibrate_k(40, 60, 96.67842872136355, 90, 3, 1.5)-reference[0]['k']) < 1e-12
    report['adapted_mit_bends'] = dict(cases=len(cases), max_length_or_bend_line_difference_mm=max(errors),
        independent_tests='tests/unfolding/test_bend_profiles.py', adopted=True,
        excludes=['generic K tables', 'die suggestions', 'material strengths'])

    # Execute the original Desarrolla geometry and check its 2D/3D edge lengths.
    folder = args.research_root/'desarrolla/src/lib/geometry'
    js = """
      import {readFileSync} from 'node:fs'; import {stripTypeScriptTypes} from 'node:module';
      const root=process.argv[1];
      const data=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
      const strip=s=>stripTypeScriptTypes(s,{mode:'strip'});
      const utils=data(strip(readFileSync(root+'/utils.ts','utf8')));
      const original=readFileSync(root+'/squareToRound.ts','utf8').replace('"./utils"',JSON.stringify(utils));
      const {developSquareToRound}=await import(data(strip(original)));
      const r=developSquareToRound({squareSide:1200,diameter:500,height:700,segments:24});
      const lines=r.unfold.paths[0].construction;const xyz=r.mesh.positions;
      let maxResidual=0,maxDiagonalResidual=0;
      for(let i=0;i<lines.length;i++){
        const [a,b]=lines[i];const flat=Math.hypot(a.x-b.x,a.y-b.y);
        const trueLength=Math.hypot(xyz[6*i]-xyz[6*i+3],xyz[6*i+1]-xyz[6*i+4],xyz[6*i+2]-xyz[6*i+5]);
        maxResidual=Math.max(maxResidual,Math.abs(flat-trueLength));
        if(i+1<lines.length){
          const c=lines[i+1][0];const flatDiagonal=Math.hypot(c.x-b.x,c.y-b.y);
          const trueDiagonal=Math.hypot(xyz[6*(i+1)]-xyz[6*i+3],xyz[6*(i+1)+1]-xyz[6*i+4],xyz[6*(i+1)+2]-xyz[6*i+5]);
          maxDiagonalResidual=Math.max(maxDiagonalResidual,Math.abs(flatDiagonal-trueDiagonal));
        }
      }
      console.log(JSON.stringify({input:{squareSide:1200,diameter:500,height:700,segments:24},
        max_generator_length_residual_mm:maxResidual,
        max_triangle_diagonal_length_residual_mm:maxDiagonalResidual,adopted:false}));
    """
    report['desarrolla_square_to_round'] = json.loads(subprocess.check_output(
        ['node', '--disable-warning=ExperimentalWarning', '--input-type=module', '-e', js, str(folder)], text=True))

    # Isolate the actual lookup method; no FreeCAD imports, UI or model writes.
    path = args.research_root/'FreeCAD_SheetMetal/SheetMetalNewUnfolder.py'
    tree = ast.parse(path.read_text())
    cls = next(v for v in tree.body if isinstance(v, ast.ClassDef) and v.name == 'BendAllowanceCalculator')
    method = next(v for v in cls.body if isinstance(v, ast.FunctionDef) and v.name == 'get_k_factor')
    scope = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), scope)
    dummy = SimpleNamespace(radius_thickness_values=[1., 3., 99.], k_factor_values=[.38, .43, .5],
                            _convert_to_ansi_kfactor=lambda v: v)
    actual = scope['get_k_factor'](dummy, 5., 1.)
    expected = .43+(.5-.43)*(5-3)/(99-3)
    assert not math.isclose(actual, expected, abs_tol=1e-6)
    report['freecad_scalar_lookup_probe'] = dict(radius_thickness=5, table=[[1,.38],[3,.43],[99,.5]],
        actual=actual, piecewise_linear_reference=expected, adopted=False,
        scope='pinned scalar get_k_factor method only; no full FreeCAD test')
    report['additional_domain_checks'] = {'python_rejects_impossible_flange': True}
    try:
        develop_profile((3.,50.), (BendInput(90.,2.,.4),),2., dimension_reference='outside')
    except ValueError:
        pass
    else:
        raise AssertionError('Impossible flange was accepted')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
