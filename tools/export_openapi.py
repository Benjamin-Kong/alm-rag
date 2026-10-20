"""Export the executed M3 contract; preserve the historical M1 snapshot."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import yaml

from almrag.api import create_app
from almrag.config import Settings

ROOT=Path(__file__).resolve().parents[1]


def as_openapi30(value):
    if isinstance(value,list):
        return [as_openapi30(item) for item in value]
    if not isinstance(value,dict):
        return value
    result={key:as_openapi30(item) for key,item in value.items()}
    if 'const' in result:
        result['enum']=[result.pop('const')]
    if 'anyOf' in result and {'type':'null'} in result['anyOf']:
        result['anyOf'].remove({'type':'null'})
        result['nullable']=True
        if len(result['anyOf'])==1:
            result.update(result.pop('anyOf')[0])
    return result


def main():
    with TemporaryDirectory() as directory:
        schema=create_app(Settings(database_path=str(Path(directory)/'schema.sqlite'))).openapi()
    (ROOT/'docs/api/m3-openapi.json').write_text(json.dumps(schema,indent=2,ensure_ascii=False)+'\n')
    path=ROOT/'docs/api/openapi.yaml'
    draft=yaml.safe_load(path.read_text())
    draft['info']['description']='M3 executed subset is marked x-implementation-status; other endpoints remain draft and unimplemented. See m3-openapi.json for the current executable contract; m1-openapi.json and m2-openapi.json are historical.'
    for methods in draft['paths'].values():
        for operation in methods.values():
            if isinstance(operation,dict) and 'operationId' in operation:
                operation.setdefault('x-implementation-status','DRAFT_NOT_IMPLEMENTED')
    for route,methods in schema['paths'].items():
        draft['paths'].setdefault(route.removeprefix('/api/v1'),{}).update(as_openapi30(methods))
    draft['components']['schemas'].update(as_openapi30(schema['components']['schemas']))
    draft['components']['securitySchemes'].update(schema['components']['securitySchemes'])
    path.write_text(yaml.safe_dump(draft,sort_keys=False,allow_unicode=True))


if __name__=='__main__':
    main()
