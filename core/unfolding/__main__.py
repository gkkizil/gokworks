"""python -m core.unfolding request.json [--format json|dxf|pdf|step|zip] --output path"""
import argparse
import json
from . import UnfoldService,ExportOptions,to_data
from .storage import read_json,request_from_dict


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request');parser.add_argument('--format',default='json',choices=('json','dxf','pdf','step','zip'))
    parser.add_argument('--output',required=True);parser.add_argument('--overwrite',action='store_true')
    parser.add_argument('--part-id',action='append',default=[]);parser.add_argument('--include-step',action='store_true')
    args=parser.parse_args();service=UnfoldService()
    try:
        request=request_from_dict(read_json(args.request));result=service.calculate(request)
        if result.status!='success':raise ValueError('; '.join(x.message for x in result.errors))
        exported=service.export(result,ExportOptions(args.output,args.format,tuple(args.part_id),args.overwrite,
            include_step=args.include_step,expected_revision=request.revision,expected_input_hash=result.input_hash))
        print(json.dumps(to_data(exported),ensure_ascii=False))
        return 0 if exported.status=='complete' else 1
    except (OSError,ValueError) as exc:
        print(json.dumps(dict(status='error',message=str(exc)),ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
